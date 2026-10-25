"""Judul/konteks halaman dan pemotongan parent-child yang menjaga batas daftar."""

import logging
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger("app.services.embedding_service")

# ── Konfigurasi Parent-Child Chunking ─────────────────────────────
_PARENT_CHUNK_SIZE = 1500
_PARENT_CHUNK_OVERLAP = 200
_CHILD_CHUNK_SIZE = 300
_CHILD_CHUNK_OVERLAP = 50


# Panjang maksimum judul dokumen yang disuntikkan sebagai konteks global ke chunk.
_DOC_TITLE_MAX_LEN = 180


def derive_document_title(pages: list[dict]) -> str | None:
    """
    Menurunkan judul dokumen dari ISI dokumen itu sendiri (halaman pertama),
    bukan dari nilai yang dipatok di kode.

    Halaman pertama dokumen resmi umumnya berupa halaman sampul yang memuat
    judul. Teksnya dirapikan (spasi/newline dipadatkan) lalu dipotong.

    Dipakai sebagai prefix "[Topik Utama: ...]" pada setiap chunk supaya halaman
    yang isinya hanya daftar panjang tetap punya konteks global. Sebelumnya
    prefix ini berisi nama satu instansi yang ditulis langsung di kode, sehingga
    dokumen dari instansi lain ikut terlabeli keliru dan embedding-nya tercemar.

    Returns:
        Judul dokumen, atau None bila tidak bisa diturunkan (lebih baik tanpa
        label sama sekali daripada label yang salah).
    """
    if not pages:
        return None

    first_page_text = (pages[0].get("text") or "").strip()
    if not first_page_text:
        return None

    # Padatkan whitespace agar judul multi-baris jadi satu baris rapi
    title = re.sub(r"\s+", " ", first_page_text).strip()
    # Buang sisa markdown bold dari hasil OCR
    title = re.sub(r"\*+", "", title).strip()

    if len(title) < 10:
        return None

    return title[:_DOC_TITLE_MAX_LEN].strip()


# ── Deteksi & pemecahan daftar (dipakai untuk parent MAUPUN child) ──
# Mengenali item berformat nomor "1." / "1)", huruf "a." / "a)", romawi "i." / "I.",
# atau bullet "- • *" — berlaku umum untuk berbagai jenis dokumen, bukan hanya
# format Diktum KEDUA pada dokumen SOP ini.
_list_item_boundary = re.compile(
    r"(?=^\s*(?:\d{1,3}[.\)]|[a-zA-Z]{1,3}[.\)]|[ivxlcdmIVXLCDM]{1,7}[.\)]|[-•*])\s+)",
    re.MULTILINE,
)
_LIST_ITEM_THRESHOLD = 10     # min. item beruntun agar halaman dianggap "daftar besar"
_LIST_BLOCK_HARD_CAP = 6000   # di atas ini daftar tetap dipecah, demi keamanan num_ctx LLM


def _split_list_preserving_items(list_text: str, max_size: int) -> list[str]:
    """
    Pecah daftar per BATAS ITEM (bukan per karakter), sehingga satu item tidak
    pernah terbelah di tengah — walau daftar keseluruhan harus dipecah karena
    melebihi max_size.

    Dipakai untuk parent (agar item tidak terpotong dari konteks LLM) dan untuk
    child (agar vektor pencarian memuat item utuh; item yang terbelah membuat
    pencarian meleset).
    """
    raw_items = _list_item_boundary.split(list_text)
    raw_items = [i.strip() for i in raw_items if i.strip()]
    out, current = [], ""
    fallback_splitter = None

    for item in raw_items:
        if current and len(current) + len(item) + 1 > max_size:
            out.append(current)
            current = ""

        if len(item) > max_size:
            # Fallback jika satu butir daftar sangat panjang melampaui max_size
            if current:
                out.append(current)
                current = ""
            if fallback_splitter is None:
                fallback_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=max_size,
                    chunk_overlap=int(max_size * 0.15),
                )
            sub_chunks = fallback_splitter.split_text(item)
            out.extend(sub_chunks)
        else:
            current = f"{current}\n{item}" if current else item

    if current:
        out.append(current)
    return out


_POLA_NAMA_SOP = re.compile(
    r"(?:(?:-\s*\*\*)?NAMA\s+SOP(?:\*\*)?\s*[:|]\s*)(.+)",
    re.IGNORECASE,
)

# Penanda bagian yang generik — TIDAK mengandaikan dokumen SOP.
#
# Bentuk 1: "LABEL :" di awal baris. Menangkap 'MEMUTUSKAN :', 'Menetapkan :',
#           'KESATU :', 'KEDUA :', dan pada dokumen lain 'Ringkasan :',
#           'Dasar Hukum :', 'Pasal 3 :'.
# Bentuk 2: baris yang seluruhnya huruf besar — judul sampul dan kepala surat.
_POLA_PENANDA_BAGIAN = re.compile(r"^[ \t]*([A-Z][^\n:]{2,58}?)[ \t]*:(?:[ \t]|$)", re.MULTILINE)
_POLA_BARIS_KAPITAL = re.compile(r"^[ \t]*([A-Z][A-Z0-9 ,\.\-()/]{4,58})[ \t]*$", re.MULTILINE)

# Baris kapital hanya dihitung bila muncul di kepala halaman. Tanpa syarat ini,
# blok tanda tangan di kaki halaman ('WALI KOTA BANDA ACEH,') merebut label
# halaman daftar yang seharusnya mewarisi bagian induknya.
_MAKS_BARIS_KEPALA = 3
_MAKS_KATA_PENANDA = 4
# Porsi minimal halaman yang harus dikuasai sebuah penanda agar ia layak
# menamai halaman itu. Setengah, bukan sepertiga: 'mewakili halaman' wajarnya
# berarti menguasai mayoritasnya. Pada sepertiga, klausul penutup 'KETIGA' di
# kaki halaman 6 lolos dengan 32% — dan 32% itu sendiri sebagian besar blok
# tanda tangan, bukan isi klausulnya.
_MIN_PORSI_PENANDA = 0.50


def derive_page_context(
    text: str,
    sebelumnya: str | None = None,
    judul_dokumen: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Label konteks untuk SATU halaman, diturunkan dari isi halaman itu sendiri.

    Halaman yang tidak punya penanda apa pun MEWARISI label halaman sebelumnya.
    Pewarisan itu bukan kemewahan: daftar 74 item pada korpus ini terbentang di
    empat halaman, dan tiga di antaranya tidak memuat satu pun baris judul.
    Tanpa warisan, tiga halaman itu masuk korpus tanpa label dan hanya bisa
    ditemukan lewat kemiripan kata — persis halaman yang paling butuh konteks.

    Urutan keputusannya, dari yang paling spesifik:

    1. Baris 'Nama SOP' — bila ada, ia judul prosedurnya dan mengalahkan yang lain.
    2. Penanda bagian TERAKHIR pada halaman. Sengaja yang terakhir, bukan yang
       pertama: halaman yang berpindah bagian di tengah diperintah oleh bagian
       yang terakhir dibuka, dan bagian itu pula yang diwariskan ke halaman
       berikutnya. Pada korpus ini halaman 3 berakhir di 'KEDUA :' yang membuka
       daftar 74 SOP, sehingga halaman 4-6 mewarisi 'KEDUA' dan bukan 'Mengingat'.
    3. Baris kapital di kepala halaman — sampul dan kepala surat.
    4. Warisan dari halaman sebelumnya.
    5. Judul dokumen, dipendekkan. Jaring terakhir supaya tidak ada halaman
       yang sama sekali tanpa konteks.
    """
    m = _POLA_NAMA_SOP.search(text)
    if m:
        nama = re.sub(r"\*+", "", m.group(1)).strip()
        if nama:
            return f"SOP {nama}", f"SOP {nama}"

    # Label penanda dibatasi 4 kata. Tanpa batas itu baris kop surat
    # 'Telepon (0651) 21855 Faximile (0651) 31980 E-mail :' ikut terjaring dan
    # merebut label halaman sampul — judul bagian yang sah praktis selalu
    # pendek ('MEMUTUSKAN', 'KEDUA', 'Dasar Hukum').
    penanda = [
        (m.group(1).strip(), m.end())
        for m in _POLA_PENANDA_BAGIAN.finditer(text)
    ]
    penanda = [
        (p, akhir) for p, akhir in penanda
        if p and not p.isdigit() and len(p.split()) <= _MAKS_KATA_PENANDA
    ]

    warisan = penanda[-1][0] if penanda else sebelumnya

    if penanda:
        label, mulai = penanda[-1]
        # Penanda yang cuma menempel di ekor halaman tidak mewakili isinya.
        # Halaman 6 korpus ini berisi 15 item daftar milik 'KEDUA' lalu ditutup
        # satu klausul 'KETIGA'; melabelinya KETIGA salah untuk 90% isinya.
        # Penanda itu tetap DIWARISKAN ke halaman berikutnya — yang membuka
        # bagian tetaplah ia — tapi bukan ia yang menamai halaman ini.
        if len(text) - mulai >= len(text) * _MIN_PORSI_PENANDA:
            return label, warisan

    if sebelumnya:
        return sebelumnya, warisan

    if penanda:
        return penanda[-1][0], warisan

    kepala = [b for b in text.split("\n") if b.strip()][:_MAKS_BARIS_KEPALA]
    for baris in kepala:
        k = _POLA_BARIS_KAPITAL.match(baris)
        if k:
            kepala_label = k.group(1).strip().rstrip(",")
            return kepala_label, (warisan or kepala_label)

    if judul_dokumen:
        judul_pendek = judul_dokumen[:60].strip()
        return judul_pendek, (warisan or judul_pendek)

    return None, warisan


def chunk_text_hierarchical(
    pages: list[dict],
    document_title: str | None = None,
    parent_chunk_size: int = _PARENT_CHUNK_SIZE,
    parent_chunk_overlap: int = _PARENT_CHUNK_OVERLAP,
    child_chunk_size: int = _CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = _CHILD_CHUNK_OVERLAP,
    strategy: str = "auto",
) -> tuple[list[dict], list[dict]]:
    """
    Memecah teks menjadi parent chunks (besar) dan child chunks (kecil).

    - Parent chunks: Dikirim ke LLM sebagai konteks yang lengkap.
    - Child chunks: Di-embed untuk pencarian semantik yang presisi.
    - Setiap child memiliki 'parent_index' yang menunjuk ke parent-nya.

    Parameter ukuran dan tumpang tindih dapat dikustomisasi secara dinamis dari API / UI.
    """
    if document_title is None:
        document_title = derive_document_title(pages)
    if document_title:
        logger.info("Judul dokumen (konteks global chunk): '%s'", document_title)
    else:
        logger.info("Judul dokumen tidak bisa diturunkan — chunk tanpa prefix topik")

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    parent_chunks: list[dict] = []
    child_chunks: list[dict] = []
    parent_index = 0
    child_index = 0

    # Pola boundary entri SOP: "**No. 1**", "**No.1**", "**No 1**", dll
    entry_pattern = re.compile(r"(?=\*\*No\.?\s*\d+\*\*)")

    # Konstanta & helper pemecah daftar kini ada di level modul (lihat
    # _split_list_preserving_items) supaya bisa dipakai untuk child juga.
    #
    # Catatan: sebelumnya _LIST_ITEM_THRESHOLD didefinisikan dua kali di sini
    # (8 lalu ditimpa 10), sehingga nilai yang benar-benar berlaku adalah 10.
    # Nilai 10 dipertahankan agar perilaku chunking tidak berubah. Pola
    # _letter_list_item yang lama dihapus karena tidak pernah dipakai.

    # Tracker Nama SOP — mendeteksi berbagai variasi format:
    # - NAMA SOP: ... (kapital semua, dari OCR plain text)
    # - - **Nama SOP**: ... (format markdown bold dari OCR lain)
    # Menggunakan IGNORECASE agar tidak terpengaruh kapitalisasi
    # Konteks halaman diwariskan antar halaman: halaman lanjutan tanpa judul
    # memakai label halaman sebelumnya. Lihat derive_page_context.
    konteks_halaman: str | None = None
    warisan_konteks: str | None = None

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        # Cek apakah ada Nama SOP di halaman ini — update jika ditemukan
        sebelum = konteks_halaman
        konteks_halaman, warisan_konteks = derive_page_context(
            text, warisan_konteks, document_title
        )
        if konteks_halaman != sebelum:
            logger.info(
                "Konteks halaman %d: '%s'", page_number, konteks_halaman
            )

        # Deteksi dulu: apakah halaman ini berisi daftar enumerasi panjang,
        # format apa pun (nomor, huruf, romawi, atau bullet)?
        list_item_count = len(_list_item_boundary.findall(text))
        is_large_list = list_item_count >= _LIST_ITEM_THRESHOLD

        if is_large_list:
            if len(text) <= _LIST_BLOCK_HARD_CAP:
                # Aman disimpan utuh sebagai SATU parent chunk — semua item ikut.
                parent_texts = [text]
                logger.info(
                    "Halaman %d terdeteksi sebagai daftar besar (%d item) "
                    "— disimpan utuh tanpa dipecah",
                    page_number, list_item_count,
                )
            else:
                # Daftar terlalu panjang untuk 1 chunk — pecah di BATAS ITEM,
                # bukan di tengah karakter, supaya tidak ada item yang terpotong.
                parent_texts = _split_list_preserving_items(text, _PARENT_CHUNK_SIZE)
                logger.info(
                    "Halaman %d: daftar besar (%d item, %d karakter) melebihi "
                    "hard cap %d — dipecah jadi %d chunk di batas item",
                    page_number, list_item_count, len(text),
                    _LIST_BLOCK_HARD_CAP, len(parent_texts),
                )
        else:
            # Coba split berdasarkan entri prosedur bernomor dulu
            parts = entry_pattern.split(text)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) <= 1:
                # Tidak ada pola "No. X", gunakan splitter biasa untuk parent
                parent_texts = parent_splitter.split_text(text)
            else:
                # Gunakan entri-entri sebagai parent chunks
                parent_texts = []
                for part in parts:
                    if len(part) <= _PARENT_CHUNK_SIZE:
                        parent_texts.append(part)
                    else:
                        parent_texts.extend(parent_splitter.split_text(part))

        for parent_text in parent_texts:
            # Suntikan konteks global, supaya halaman yang isinya hanya daftar panjang
            # tetap terhubung ke dokumen induknya. Judul diturunkan dari dokumen itu
            # sendiri (lihat derive_document_title), BUKAN dipatok di kode — kalau
            # dipatok, dokumen instansi lain ikut terlabeli keliru.
            prefix = f"[Halaman {page_number}]"
            if document_title:
                prefix += f"\n[Topik Utama: {document_title}]"
            if konteks_halaman:
                prefix += f"\n[Konteks: {konteks_halaman}]"

            parent_text_with_meta = f"{prefix}\n{parent_text}"
            parent_chunks.append({
                "text": parent_text_with_meta,
                "page_number": page_number,
                "chunk_index": parent_index,
            })

            # Pecah parent menjadi child chunks yang lebih kecil.
            # Pada halaman berisi daftar, pemecahan dilakukan di BATAS ITEM —
            # splitter berbasis karakter bisa membelah satu item ke dua child,
            # dan item yang terbelah membuat vektornya tidak lagi mewakili item
            # itu secara utuh sehingga pencarian meleset.
            if is_large_list:
                child_texts = _split_list_preserving_items(parent_text, _CHILD_CHUNK_SIZE)
            else:
                child_texts = child_splitter.split_text(parent_text)
            for ct in child_texts:
                child_text_with_meta = f"{prefix}\n{ct}"
                child_chunks.append({
                    "text": child_text_with_meta,
                    "page_number": page_number,
                    "chunk_index": child_index,
                    "parent_index": parent_index,
                })
                child_index += 1

            parent_index += 1

    logger.info(
        "Hierarchical chunking: %d parent, %d child dari %d halaman",
        len(parent_chunks), len(child_chunks), len(pages),
    )
    return parent_chunks, child_chunks
