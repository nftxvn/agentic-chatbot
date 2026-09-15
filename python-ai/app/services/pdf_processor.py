"""
Service untuk memproses file PDF dan mengekstrak gambar secara umum.
Tidak lagi terbatas pada tabel SOP.
"""

import base64
import logging
import re
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF
import requests
import time

from app.config import settings

logger = logging.getLogger(__name__)

# Threshold minimum jumlah karakter untuk dianggap sebagai halaman teks murni
# Ditingkatkan ke 300 agar halaman SOP (yang sebagian besar flowchart/gambar tapi punya header teks)
# tetap dikirim ke vision pipeline agar tidak terlewat.
_MIN_TEXT_LENGTH = 300

# Perbesaran render halaman. SATU angka untuk dua pemakaian yang harus sama:
# gambar yang dibaca model vision, dan gambar bawaan yang dilihat korektor di
# editor web.
#
# Kesamaan itu bukan kebetulan melainkan syarat. Bila korektor melihat gambar
# yang lebih tajam daripada yang dibaca model, ia akan memperbaiki teks yang
# MUSTAHIL terbaca model lalu mengira masalahnya selesai — padahal itu pertanda
# resolusi render yang kurang, dan obatnya menaikkan angka ini, bukan menyuruh
# orang mengetik ulang ratusan halaman.
#
# Dengan resolusi yang sama, penyebabnya langsung terbaca:
#   korektor bisa baca, model tidak  -> model yang gagal
#   korektor juga tidak bisa baca    -> render yang kurang tajam
ZOOM_OCR = 2.0

# Perbesaran yang boleh diminta lewat API. Daftar tertutup, bukan rentang:
# tanpa batas, satu permintaan zoom=50 membuat server merender gambar 46.000
# piksel dan kehabisan memori.
ZOOM_DIIZINKAN = (1.5, 2.0, 3.0, 4.0)

# JPEG, bukan PNG. Halaman pindaian itu foto — ada bintik dan gradasi abu di
# tepi huruf — sehingga PNG jadi tiga kali lebih besar untuk hasil yang
# terlihat sama. Terukur pada halaman 936x612 pt: 577 KB lawan 186 KB.
# Kualitas 80, bukan 65: yang lebih rendah hanya menghemat 20% lagi tapi mulai
# memakan goresan tipis, dan digit NIP yang pertama rusak.
_MUTU_JPEG = 80


def _resolve_pdf_path(file_path: str) -> str:
    """Mencari lokasi fisik berkas dokumen di berbagai kemungkinan path storage."""
    if not file_path:
        raise FileNotFoundError("Path berkas kosong")

    p = Path(file_path)
    if p.exists() and p.is_file():
        return str(p)

    filename = p.name
    candidates = [
        Path("/var/www/html/storage/app/private/documents") / filename,
        Path("/var/www/html/storage/app/documents") / filename,
        Path("/var/www/html/storage/app/private") / filename,
        Path("/var/www/html/storage/app") / filename,
        Path("/app/data/uploads") / filename,
        Path("/app/uploads") / filename,
        Path("./laravel-admin/storage/app/private/documents") / filename,
        Path("./laravel-admin/storage/app/documents") / filename,
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return str(cand)

    norm = file_path.replace("\\", "/")
    if "storage/" in norm:
        rel = norm.split("storage/", 1)[1]
        cand = Path("/var/www/html/storage") / rel
        if cand.exists() and cand.is_file():
            return str(cand)

    raise FileNotFoundError(f"Berkas tidak ditemukan: {file_path}")


def render_halaman(
    file_path: str, page_number: int, zoom: float = ZOOM_OCR
) -> tuple[bytes, int, int]:
    """
    Render satu halaman PDF jadi JPEG.

    Args:
        file_path: berkas PDF.
        page_number: nomor halaman, dihitung dari 1 — sama seperti yang dilihat
            pengguna dan yang dipakai di seluruh API. PyMuPDF memakai indeks 0;
            penyesuaiannya dikerjakan di sini, satu kali, supaya pemanggil tidak
            perlu mengingatnya.
        zoom: perbesaran. Harus salah satu dari ZOOM_DIIZINKAN.

    Returns:
        (data JPEG, lebar piksel, tinggi piksel)

    Raises:
        FileNotFoundError: berkas tidak ada.
        ValueError: nomor halaman di luar jangkauan, atau zoom tidak diizinkan.
    """
    if zoom not in ZOOM_DIIZINKAN:
        raise ValueError(
            f"zoom {zoom} tidak diizinkan. Pilih salah satu: "
            f"{', '.join(str(z) for z in ZOOM_DIIZINKAN)}"
        )

    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError(
                f"Halaman {page_number} di luar jangkauan (dokumen ini {len(doc)} halaman)"
            )

        pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("jpeg", jpg_quality=_MUTU_JPEG), pix.width, pix.height


def ukuran_halaman(file_path: str) -> list[dict]:
    """
    Lebar dan tinggi tiap halaman pada perbesaran bawaan, tanpa merender apa pun.

    Dipakai editor web untuk menyiapkan ukuran panel sebelum gambarnya sampai.
    Tanpa ini panel berkedip menyesuaikan ukuran tiap kali pindah halaman —
    dan pada dokumen ini kedipannya nyata, karena 6 dari 171 halaman potret
    sementara sisanya lanskap.
    """
    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        return [
            {
                "page_number": i + 1,
                "lebar": round(h.rect.width * ZOOM_OCR),
                "tinggi": round(h.rect.height * ZOOM_OCR),
                "orientasi": "lanskap" if h.rect.width >= h.rect.height else "potret",
            }
            for i, h in enumerate(doc)
        ]



def detect_pdf_type(file_path: str) -> str:
    """
    Mendeteksi tipe PDF berdasarkan konten setiap halaman.
    """
    file_path = _resolve_pdf_path(file_path)

    try:
        doc = fitz.open(file_path)
        has_text_pages = False
        has_scanned_pages = False

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()

            if len(text) >= _MIN_TEXT_LENGTH:
                has_text_pages = True
            else:
                image_list = page.get_images(full=True)
                if image_list:
                    has_scanned_pages = True
                else:
                    has_scanned_pages = True

        doc.close()

        if has_text_pages and has_scanned_pages:
            pdf_type = "mixed"
        elif has_scanned_pages:
            pdf_type = "scanned"
        else:
            pdf_type = "text"

        logger.info("Tipe PDF '%s' terdeteksi: %s", file_path, pdf_type)
        return pdf_type

    except Exception as e:
        logger.error("Gagal mendeteksi tipe PDF '%s': %s", file_path, str(e))
        raise


def _extract_text_from_page(page: fitz.Page) -> str:
    """
    Ekstrak teks dan tabel dari halaman secara native dengan PyMuPDF.
    Hanya membaca teks — tidak mencoba membaca gambar flowchart.
    """
    tabs = page.find_tables()

    if not tabs.tables:
        return page.get_text().strip()

    elements = []
    table_bboxes = []

    for tab in tabs:
        table_bboxes.append(tab.bbox)
        rows = tab.extract()

        # Convert ke Markdown
        md_table = []
        for r in rows:
            cleaned_row = [str(c).replace("\n", " ").replace("|", "/").strip() if c else "-" for c in r]
            md_table.append("| " + " | ".join(cleaned_row) + " |")

        if len(rows) > 0:
            sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
            md_table.insert(1, sep)

        elements.append({
            "type": "table",
            "y0": tab.bbox[1],
            "content": "\n".join(md_table)
        })

    # Ekstrak blocks teks biasa (di luar tabel)
    blocks = page.get_text("blocks")
    for b in blocks:
        b_rect = fitz.Rect(b[:4])
        b_text = b[4].strip()

        if not b_text:
            continue

        in_table = False
        for t_bbox in table_bboxes:
            t_rect = fitz.Rect(t_bbox)
            if t_rect.intersects(b_rect):
                in_table = True
                break

        if not in_table:
            elements.append({
                "type": "text",
                "y0": b_rect.y0,
                "content": b_text
            })

    # Urutkan berdasarkan posisi Y (dari atas ke bawah)
    elements.sort(key=lambda x: x["y0"])
    return "\n\n".join([e["content"] for e in elements])


def _strip_garbage(text: str) -> str:
    """Hapus tag HTML dan base64 image dari output LLM, tanpa merusak tabel Markdown."""
    text = re.sub(r'<img[^>]+/?>', '', text)
    
    # Bersihkan markdown code fences (misalnya ```markdown ... ```)
    if text.startswith("```"):
        lines = text.split('\n')
        if len(lines) > 2:
            text = '\n'.join(lines[1:-1])
    
    return text.strip()


# ── Prompt OCR: dasar yang generik, petunjuk format yang opsional ────
#
# Layanan ini menerima dokumen APA PUN yang diunggah admin. Prompt bawaannya
# karena itu tidak boleh mengandaikan satu bentuk dokumen tertentu: mengatakan
# kepada model bahwa "dokumen ini terdiri dari HEADER dan TABEL PROSEDUR"
# membuatnya mencari struktur yang tidak ada pada notulen, surat, atau laporan —
# dan model yang diminta mencari sesuatu cenderung menemukannya walau tidak ada.
#
# Petunjuk khusus formulir hanya ditempelkan bila dokumennya memang terdeteksi
# berbentuk demikian (lihat `_terlihat_formulir_sop`).

_PROMPT_OCR_DASAR = (
    "Anda adalah sistem OCR. Salin SELURUH teks yang terlihat pada gambar ini.\n\n"

    "ATURAN:\n"
    "- Salin apa adanya. JANGAN meringkas, menafsirkan, atau menambahkan apa pun "
    "yang tidak tertulis di gambar.\n"
    "- Pertahankan urutan baca dokumen: atas ke bawah, kiri ke kanan.\n"
    "- Pertahankan penanda daftar PERSIS seperti tertulis (`1.`, `a.`, `aa.`, "
    "`iii.`). Jangan menomori ulang, jangan menyeragamkan.\n"
    "- Tulis isi tabel sebagai teks biasa atau daftar. JANGAN memakai tabel "
    "Markdown (tanda |).\n"
    "- Bila sebuah sel kosong, biarkan kosong. Jangan menebak isinya.\n"
    "- HANYA keluarkan teks hasil ekstraksi, tanpa penjelasan atau komentar.\n"
)

# Petunjuk formulir SOP dipecah dua karena keduanya punya jangkauan berbeda.
#
# Bagian TABEL berlaku untuk seluruh halaman lanjutan formulir: halaman kedua
# sebuah SOP tidak memuat kepala apa pun, tapi tetap butuh aturan format
# langkah prosedurnya. Bagian ini karena itu lengket antar halaman.
#
# Bagian KEPALA hanya boleh dipakai pada halaman yang KEPALANYA MEMANG ADA.
# Sebelumnya keduanya menyatu dan sama-sama lengket, sehingga halaman 8 dan 10
# — murni tabel prosedur tanpa kepala — tetap menerima instruksi "WAJIB: baris
# 'Nama SOP' PASTI ada, JANGAN melewatkan". Model menurutinya dengan MENGARANG
# kepala: 'Nomor SOP: 001' dan nama SOP yang disadur dari teks langkah pertama.
# Instruksi yang benar untuk halaman berkepala menjadi racun untuk halaman
# tanpa kepala.
_PETUNJUK_TABEL_SOP = (
    "\nHALAMAN INI BERBENTUK FORMULIR SOP PEMERINTAH. Ikuti tambahan berikut.\n\n"

    "BAGIAN TABEL PROSEDUR (Uraian Prosedur / Langkah-langkah):\n"
    "HANYA UNTUK TABEL YANG MEMILIKI KOLOM 'Uraian Prosedur', 'Pelaksana', dan 'Mutu Baku', gunakan format ini PERSIS untuk setiap langkah:\n"
    "- <Nomor>. <Uraian Prosedur>\n"
    "  - Pelaksana: <nama jabatan yang ada centang/simbol di kolomnya>\n"
    "  - Kelengkapan: <isi kolom Kelengkapan>\n"
    "  - Waktu: <isi kolom Waktu>\n"
    "  - Output: <isi kolom Output>\n\n"

    "ATURAN TAMBAHAN:\n"
    "- Pelaksana ditentukan dari POSISI simbol flowchart (kotak/belah ketupat). Lihat simbol berada di bawah kolom jabatan mana.\n"
    "- Waktu dan Output adalah DUA kolom BERBEDA. JANGAN digabung. (Contoh BENAR: Waktu: 30 menit / Output: Disposisi).\n"
    "- Bila halaman ini TIDAK memuat kepala formulir ('Nomor SOP', 'Nama SOP', "
    "'Disahkan Oleh'), JANGAN membuatnya. Halaman lanjutan memang tidak punya kepala; "
    "menuliskannya berarti mengarang.\n"
)

_PETUNJUK_KEPALA_SOP = (
    "\nBAGIAN KEPALA FORMULIR (Teks Biasa & Daftar):\n"
    "Bagian seperti 'Nomor SOP', 'Nama SOP', 'Tanggal Pembuatan', 'Tanggal Pengesahan', 'Disahkan Oleh', "
    "'Dasar Hukum', 'Kualifikasi Pelaksana', 'Keterkaitan', 'Peralatan/Perlengkapan', "
    "dan 'Peringatan' BUKAN TABEL PROSEDUR. Tulis bagian ini SEBAGAI TEKS BIASA ATAU DAFTAR (LIST) NORMAL. "
    "DILARANG KERAS menambahkan atribut 'Pelaksana', 'Kelengkapan', 'Waktu', atau 'Output' pada bagian ini!\n\n"

    "WAJIB: bila halaman memuat 'Nomor SOP', maka baris 'Nama SOP' PASTI ada di kepala tabel yang sama — "
    "salin keduanya. JANGAN melewatkan 'Nama SOP'. Baris itu adalah judul prosedurnya dan tanpanya "
    "halaman ini tidak bisa dikenali.\n\n"

    # Sel 'Disahkan Oleh' berisi EMPAT baris bertumpuk, bukan satu nilai. Model
    # yang menulis kepala sebagai daftar 'Field: nilai' mengambil baris pertama
    # saja lalu pindah ke field berikutnya, dan nama pejabat beserta NIP-nya —
    # yang menempati dua pertiga bawah sel yang sama — hilang tanpa jejak.
    # Terukur: dari empat kali ekstraksi halaman berkepala, hanya SATU yang
    # menyalinnya, dan itu satu-satunya yang tidak memakai bentuk 'Field: nilai'.
    "WAJIB: sel 'Disahkan Oleh' memuat BEBERAPA BARIS bertumpuk — nama jabatan, "
    "lalu NAMA PEJABAT, lalu PANGKAT, lalu 'NIP.' beserta nomornya. Salin SEMUA "
    "barisnya, masing-masing pada baris sendiri. JANGAN berhenti setelah baris "
    "jabatan. Nama pejabat dan baris NIP sering tertindih stempel atau coretan "
    "tanda tangan — tetap salin, jangan dilewati.\n\n"

    "Tulis tiap bagian kepala sebagai baris terpisah, JANGAN memampatkan satu sel "
    "berisi banyak baris menjadi satu baris tunggal.\n"
)

# Penanda kepala formulir SOP pemerintah (template Permenpan 35/2012).
# Dipakai untuk memutuskan apakah petunjuk di atas layak ditempelkan.
_PENANDA_FORMULIR_SOP = ("nomor sop", "nama sop", "uraian prosedur", "mutu baku")
_MIN_PENANDA_FORMULIR = 2


def _terlihat_formulir_sop(text: str) -> bool:
    """
    Apakah teks hasil OCR menunjukkan halaman berformat formulir SOP?

    Dua penanda disyaratkan, bukan satu: kata 'nama sop' saja bisa muncul di
    dokumen mana pun yang kebetulan membahas SOP, sedangkan kombinasi seperti
    'nomor sop' + 'mutu baku' praktis hanya ada pada formulirnya sendiri.
    """
    rendah = text.lower()
    return sum(p in rendah for p in _PENANDA_FORMULIR_SOP) >= _MIN_PENANDA_FORMULIR


# Penanda tempat daftar kata kunci disisipkan bila admin menuliskannya sendiri
# di dalam prompt kategori. `{job_titles}` dipertahankan karena kategori lama
# sudah memakainya — mengganti nama tidak boleh mematikan data yang sudah ada.
_POLA_KATA_KUNCI = ("{kata_kunci}", "{job_titles}")


def _sisipkan_kata_kunci(prompt: str, kata_kunci: str) -> str:
    """
    Masukkan daftar kata kunci ke dalam prompt.

    Dua jalur, dan yang kedua yang membuatnya tidak bisa gagal diam-diam:
    ditulis sebagai penanda -> disisipkan PERSIS di posisi itu, sehingga admin
    mengendalikan letaknya; tidak ditulis (atau salah ketik) -> ditempelkan di
    akhir sebagai blok. Daftar yang sudah diisi admin tidak pernah hilang hanya
    karena penandanya keliru.
    """
    if not kata_kunci:
        return prompt

    for pola in _POLA_KATA_KUNCI:
        if pola in prompt:
            return prompt.replace(pola, kata_kunci)

    # Daftar telanjang tidak cukup: diuji pada halaman 8 SOP FULL, model tetap
    # menulis "Renatra" walau "Renstra" ada di daftar. Model perlu diberi tahu
    # apa yang harus DILAKUKAN dengan daftar itu, bukan sekadar disodori.
    # Kalimatnya juga membatasi diri — "hanya bila memang mirip" — supaya model
    # tidak memaksakan istilah dari daftar ke kata yang sebenarnya berbeda.
    return prompt + (
        "\n[ISTILAH & JABATAN RESMI]\n"
        "Dokumen ini memakai istilah berikut. Bila sebuah kata terbaca MIRIP "
        "salah satunya, tulis persis seperti daftar ini. Bila tidak mirip, "
        "salin apa adanya — jangan memaksakan istilah dari daftar.\n"
        f"{kata_kunci}\n"
    )


def vision_extract_general(
    img_base64: str,
    retries: int = 3,
    petunjuk: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> str:
    """
    Ekstraksi teks satu halaman gambar lewat model vision.

    Prompt disusun berlapis, dan urutannya disengaja:
        aturan dasar  ->  tambahan dari kategori  ->  petunjuk otomatis
    Prompt kategori MENAMBAH, tidak menggantikan. Aturan dasar memuat penjaga
    yang tidak boleh hilang (jangan menomori ulang, jangan menebak sel kosong),
    dan petunjuk otomatis memuat penjaga anti-karangan untuk halaman lanjutan
    formulir SOP yang tidak punya kepala.

    Args:
        img_base64: Halaman yang sudah dirender, dalam base64.
        retries: Percobaan ulang bila panggilan HTTP-nya gagal.
        petunjuk: Petunjuk format tambahan yang ditempelkan ke prompt dasar.
            Dibiarkan None untuk dokumen umum — itu jalur bawaannya.
        category_prompt: Panduan/instruksi khusus dari kategori dokumen di Laravel.
        job_titles: Daftar kata kunci/jabatan resmi dari kategori dokumen, sudah
            berbentuk teks dipisah koma.
        vision_model: Model vision spesifik kategori (opsional).
        custom_prompts: Kamus prompt kustom untuk menimpa aturan bawaan secara dinamis.
    """
    logger.info("Using general vision extraction pipeline...")

    prompt_dasar = (custom_prompts.get("dasar") if custom_prompts else None) or _PROMPT_OCR_DASAR
    prompt = prompt_dasar
    if category_prompt:
        prompt += f"\n\n[PANDUAN KHUSUS KATEGORI DOKUMEN]:\n{category_prompt}\n"
    prompt = _sisipkan_kata_kunci(prompt, job_titles or "")
    if petunjuk:
        prompt += f"\n{petunjuk}"

    model_to_use = vision_model or settings.VISION_MODEL_NAME

    payload = {
        "model": model_to_use,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "options": {
            "num_ctx": 4096, 
            "num_predict": 2048, 
            "temperature": 0.1
        }
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=settings.VISION_TIMEOUT)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            if raw:
                return _strip_garbage(raw)
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"Attempt {attempt}/{retries}: Timeout/Error saat vision extract: {e}")
            time.sleep(2)

    if last_error:
        raise RuntimeError(f"Gagal melakukan Vision OCR: {last_error}")
    raise RuntimeError("Model Vision OCR mengembalikan teks kosong")


# ── Penjaga kelengkapan hasil OCR ────────────────────────────────
#
# Halaman formulir SOP selalu memuat pasangan "Nomor SOP" dan "Nama SOP" di
# kepala tabel yang sama. Model vision kadang menjatuhkan salah satunya, dan
# yang hilang TIDAK menimbulkan galat apa pun: dokumen tetap ter-ingest, hanya
# saja halaman itu kehilangan label SOP-nya (lihat sop_name_pattern di
# embedding_service) sehingga tidak pernah ditemukan ketika ditanya memakai
# nama SOP tersebut.
#
# Kegagalan sunyi seperti ini yang paling mahal: sudah terjadi sekali pada
# halaman SOP Renstra, dan baru ketahuan lewat jawaban "tidak ditemukan"
# padahal dokumennya memuat jawabannya.
_OCR_ULANG_MAKS = 2


# Baris NIP pada blok pengesahan. Dipisah supaya penjaga di bawah bisa
# membedakan "kepala formulir ada tapi blok tanda tangannya jatuh" dari
# "halaman ini memang bukan formulir".
_POLA_NIP = re.compile(r"\bNIP\.?\s*:?\s*\d{6,}", re.IGNORECASE)


def _kepala_sop_terlihat(text: str) -> bool:
    """Halaman ini memuat kepala formulir SOP — bukan sekadar tabel lanjutan."""
    return "nomor sop" in text.lower()


def _header_sop_tidak_lengkap(text: str) -> bool:
    """
    Kepala formulir terbaca sebagian — hasil OCR cacat dan layak diulang.

    Dua bentuk kehilangan diperiksa, keduanya hanya berlaku bila 'Nomor SOP'
    memang ada di halaman itu:

    1. 'Nama SOP' hilang — halaman kehilangan label prosedurnya, sehingga tidak
       pernah ditemukan ketika ditanya memakai nama SOP tersebut.
    2. Baris 'NIP.' hilang — sel 'Disahkan Oleh' memuat empat baris bertumpuk
       (jabatan, nama pejabat, pangkat, NIP) dan model yang menulis kepala
       sebagai daftar 'Field: nilai' hanya mengambil baris pertama. Terukur:
       dari empat kali ekstraksi halaman berkepala, tiga menjatuhkan blok itu
       dan LOLOS penjaga lama tanpa satu pun peringatan — persis kegagalan
       sunyi yang penjaga ini dibuat untuk mencegahnya, tapi hanya untuk satu
       baris yang kebetulan sudah pernah hilang lebih dulu.

    Halaman dokumen umum tidak memuat 'Nomor SOP' sama sekali, jadi keduanya
    langsung bernilai salah — tidak ada OCR ulang, tidak ada yang ditandai gagal.
    """
    if not _kepala_sop_terlihat(text):
        return False
    return "nama sop" not in text.lower() or not _POLA_NIP.search(text)


def _bagian_kepala_hilang(text: str) -> str:
    """Sebutkan bagian mana yang hilang, untuk pesan log yang bisa ditindaklanjuti."""
    kurang = []
    if "nama sop" not in text.lower():
        kurang.append("'Nama SOP'")
    if not _POLA_NIP.search(text):
        kurang.append("baris 'NIP.'")
    return " dan ".join(kurang) if kurang else "-"


def _ocr_dengan_penjaga(
    img_base64: str,
    page_label: int,
    petunjuk: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> str:
    """
    Menjalankan ekstraksi vision, mengulang bila kepala tabel SOP jelas tidak lengkap.

    Pengulangan masuk akal karena keluaran model vision tidak deterministik:
    halaman yang sama bisa menghasilkan isi berbeda tiap kali, dan percobaan
    berikutnya kerap menangkap baris yang tadi terlewat.

    Penjaganya membatasi dirinya sendiri: `_header_sop_tidak_lengkap` hanya
    bernilai benar bila 'Nomor SOP' ADA tetapi 'Nama SOP' atau baris 'NIP.'
    hilang. Halaman dokumen umum tidak memuat 'Nomor SOP' sama sekali, jadi
    langsung kembali pada percobaan pertama — tidak ada OCR ulang, tidak ada
    yang ditandai gagal.
    """
    text = vision_extract_general(
        img_base64,
        petunjuk=petunjuk,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    for percobaan in range(1, _OCR_ULANG_MAKS + 1):
        if not _header_sop_tidak_lengkap(text):
            return text

        logger.warning(
            "Halaman %d: kepala formulir terbaca tetapi %s hilang — OCR diulang (%d/%d)",
            page_label, _bagian_kepala_hilang(text), percobaan, _OCR_ULANG_MAKS,
        )
        ulang = vision_extract_general(
            img_base64,
            petunjuk=petunjuk,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

        if not _header_sop_tidak_lengkap(ulang):
            logger.info("Halaman %d: kepala formulir lengkap pada pengulangan ke-%d",
                        page_label, percobaan)
            return ulang

        # Sama-sama cacat — simpan yang paling banyak isinya.
        if len(ulang) > len(text):
            text = ulang

    logger.error(
        "Halaman %d tetap kehilangan %s setelah %d percobaan. Bila yang hilang "
        "'Nama SOP', halaman ini tidak akan mendapat label SOP dan sulit ditemukan "
        "lewat nama prosedurnya; bila yang hilang baris 'NIP.', blok pengesahan "
        "tidak akan bisa dijawab.",
        page_label, _bagian_kepala_hilang(text), _OCR_ULANG_MAKS + 1,
    )
    return text




# ─────────────────────────────────────────────────────────────
# PERBAIKAN PENANDA DAFTAR HASIL OCR
# ─────────────────────────────────────────────────────────────

_POLA_PENANDA_HURUF = re.compile(
    r"(?m)^(\s*)([A-Za-z]{1,2})\.(\s+)"
)

_MIN_RUNTUN_UNTUK_PERBAIKAN = 3


def perbaiki_penanda_daftar(pages_content: list[dict]) -> int:
    """
    Memulihkan penanda daftar bertingkat yang dipotong model vision.
    """
    keadaan = {
        "terakhir": None,
        "panjang_runtun": 0,
        "diperbaiki": 0,
    }

    def tangani(m: re.Match) -> str:
        spasi_awal, penanda, spasi_akhir = m.group(1), m.group(2), m.group(3)
        rendah = penanda.lower()
        terakhir = keadaan["terakhir"]

        if terakhir is None:
            keadaan["terakhir"] = rendah
            keadaan["panjang_runtun"] = 1
            return m.group(0)

        panjang = len(terakhir)
        huruf_terakhir = terakhir[0]
        huruf_berikutnya = chr(ord(huruf_terakhir) + 1)
        diharapkan = huruf_berikutnya * panjang

        if rendah == diharapkan:
            keadaan["terakhir"] = rendah
            keadaan["panjang_runtun"] += 1
            return m.group(0)

        boleh_perbaiki = (
            rendah[0] == diharapkan[0]
            and keadaan["panjang_runtun"] >= _MIN_RUNTUN_UNTUK_PERBAIKAN
        )
        if boleh_perbaiki:
            keadaan["terakhir"] = diharapkan
            keadaan["panjang_runtun"] += 1
            keadaan["diperbaiki"] += 1
            logger.info("Penanda daftar diperbaiki: '%s.' -> '%s.'", penanda, diharapkan)
            return f"{spasi_awal}{diharapkan}.{spasi_akhir}"

        keadaan["terakhir"] = rendah            # daftar lain — mulai runtun baru
        keadaan["panjang_runtun"] = 1
        return m.group(0)

    for halaman in pages_content:
        halaman["text"] = _POLA_PENANDA_HURUF.sub(tangani, halaman["text"])

    if keadaan["diperbaiki"]:
        logger.info(
            "%d penanda daftar dipulihkan — huruf ulangnya rontok saat OCR",
            keadaan["diperbaiki"],
        )
    return keadaan["diperbaiki"]


def _ekstrak_halaman(
    page: "fitz.Page",
    nomor: int,
    petunjuk_tabel: str | None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> tuple[str, str | None]:
    """
    Ekstrak SATU halaman. Satu-satunya tempat logika per halaman ditulis.
    """
    text = _extract_text_from_page(page)
    if len(text) >= _MIN_TEXT_LENGTH:
        return text, petunjuk_tabel

    logger.info(
        "Halaman %d: teks minim (%d karakter), memulai vision pipeline umum...",
        nomor, len(text),
    )

    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img_base64 = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=85)).decode("utf-8")

    tabel_rule = (custom_prompts.get("tabel_sop") if custom_prompts else None) or _PETUNJUK_TABEL_SOP
    kepala_rule = (custom_prompts.get("kepala_sop") if custom_prompts else None) or _PETUNJUK_KEPALA_SOP

    petunjuk_awal = petunjuk_tabel
    text = vision_extract_general(
        img_base64,
        petunjuk=petunjuk_tabel,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    kepala = kepala_rule if _kepala_sop_terlihat(text) else ""

    if petunjuk_tabel is None and _terlihat_formulir_sop(text):
        logger.info(
            "Halaman %d terdeteksi berformat formulir SOP — petunjuk tabel "
            "prosedur diaktifkan untuk halaman berikutnya.",
            nomor,
        )
        petunjuk_tabel = tabel_rule

    petunjuk_penuh = (petunjuk_tabel or "") + kepala
    if petunjuk_penuh and petunjuk_penuh != (petunjuk_awal or ""):
        if kepala:
            logger.info(
                "Halaman %d memuat kepala formulir — dibaca ulang dengan "
                "petunjuk kepala.",
                nomor,
            )
        text = _ocr_dengan_penjaga(
            img_base64,
            nomor,
            petunjuk_penuh,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    return text, petunjuk_tabel


def ekstrak_gambar_uji(
    img_base64: str,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> dict:
    """
    Jalankan SATU gambar lepas lewat jalur vision yang sama persis dengan produksi.

    Ada supaya sandbox "Uji Prompt" di admin tidak lagi punya implementasi
    sendiri. Sebelumnya sandbox memakai prompt kategori sebagai PENGGANTI aturan
    dasar dan tidak punya deteksi formulir SOP sama sekali — sehingga hasil uji
    bisa jauh berbeda dari hasil ekstraksi sungguhan, dan admin menyetel
    promptnya berdasarkan hasil yang menyesatkan.

    Satu perbedaan tetap ada dan memang tidak terhindarkan: di produksi petunjuk
    tabel SOP menempel antar halaman (halaman lanjutan mewarisi dari halaman
    sebelumnya), sedangkan di sini hanya ada satu gambar sehingga deteksinya
    berlaku untuk gambar itu saja. Itu dilaporkan lewat `petunjuk_aktif` supaya
    terlihat, bukan disembunyikan.

    Returns:
        dict berisi `teks` (hasil akhir), `teks_awal` (bacaan pertama sebelum
        petunjuk otomatis dipasang), dan `petunjuk_aktif` (daftar nama petunjuk
        yang menyala).
    """
    tabel_rule = (custom_prompts.get("tabel_sop") if custom_prompts else None) or _PETUNJUK_TABEL_SOP
    kepala_rule = (custom_prompts.get("kepala_sop") if custom_prompts else None) or _PETUNJUK_KEPALA_SOP

    teks_awal = vision_extract_general(
        img_base64,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    # Urutan pemeriksaannya sama dengan _ekstrak_satu_halaman: petunjuk dipilih
    # dari ISI bacaan pertama, bukan dari setelan kategori.
    tabel = tabel_rule if _terlihat_formulir_sop(teks_awal) else ""
    kepala = kepala_rule if _kepala_sop_terlihat(teks_awal) else ""

    aktif = []
    if tabel:
        aktif.append("tabel prosedur SOP")
    if kepala:
        aktif.append("kepala formulir SOP")

    teks = teks_awal
    petunjuk_penuh = tabel + kepala
    if petunjuk_penuh:
        teks = _ocr_dengan_penjaga(
            img_base64,
            1,
            petunjuk_penuh,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    return {"teks": teks, "teks_awal": teks_awal, "petunjuk_aktif": aktif}


def ekstrak_satu_halaman(
    file_path: str,
    page_number: int,
    petunjuk_tabel: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> tuple[str, str | None]:
    """
    Ekstrak satu halaman, membawa petunjuk format dari panggilan sebelumnya.
    """
    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError(
                f"Halaman {page_number} di luar jangkauan "
                f"(dokumen ini {len(doc)} halaman)"
            )
        return _ekstrak_halaman(
            doc[page_number - 1],
            page_number,
            petunjuk_tabel,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )


def extract_text(
    file_path: str,
    page_num: int | None = None,
    progress_callback: Callable | None = None,
) -> list[dict]:
    """
    Mengekstrak teks dari seluruh halaman PDF.
    - Halaman teks: PyMuPDF langsung.
    - Halaman scan: Ekstrak menggunakan Ollama Vision Model secara umum.
    """
    file_path = _resolve_pdf_path(file_path)

    pages_content: list[dict] = []

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        if page_num is not None:
            pages_to_process = [page_num]
            logger.info("Memproses PDF '%s' (hanya halaman %d)", file_path, page_num + 1)
        else:
            pages_to_process = list(range(total_pages))
            logger.info("Memproses PDF '%s' (%d halaman)", file_path, total_pages)

        # Petunjuk format ditemukan dari dokumennya sendiri, bukan diandaikan.
        petunjuk_tabel: str | None = None

        for count, p_idx in enumerate(pages_to_process, start=1):
            if p_idx >= total_pages:
                logger.warning(f"Halaman {p_idx + 1} di luar jangkauan (total {total_pages}).")
                continue

            text, petunjuk_tabel = _ekstrak_halaman(
                doc[p_idx], p_idx + 1, petunjuk_tabel
            )

            if text:
                pages_content.append({
                    "page_number": p_idx + 1,
                    "text": text,
                })

            if progress_callback is not None:
                try:
                    progress_callback(count, total_pages, p_idx + 1, text)
                except TypeError:
                    try:
                        progress_callback(count, total_pages)
                    except Exception as cb_err:
                        logger.warning("Error saat memanggil progress_callback: %s", cb_err)
                except Exception as cb_err:
                    logger.warning("Error saat memanggil progress_callback: %s", cb_err)

        doc.close()

        # Dijalankan setelah SELURUH halaman terkumpul: daftar menyeberang
        # halaman, jadi penanda pertama sebuah halaman hanya bisa disimpulkan
        # dari penanda terakhir halaman sebelumnya.
        perbaiki_penanda_daftar(pages_content)

        logger.info("Berhasil mengekstrak teks dari %d/%d halaman PDF '%s'", len(pages_content), total_pages, file_path)
        return pages_content

    except Exception as e:
        logger.error("Gagal mengekstrak teks dari PDF '%s': %s", file_path, str(e))
        raise
