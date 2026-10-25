"""Penjaga konteks, daftar lengkap, dan petunjuk jawaban berbasis dokumen."""

import logging
import re

_re = re
logger = logging.getLogger("app.services.rag_service")

_SOP_DETAIL_MARKERS = [
    "Dasar Hukum:", "Kualifikasi Pelaksana:", "Peralatan/Perlengkapan:",
    "Pelaksana:", "Kelengkapan:",
]

_PROCEDURE_QUESTION_KEYWORDS = ["prosedur", "langkah", "bagaimana cara", "tahapan", "tata cara"]






# ─────────────────────────────────────────────────────────────
# DETEKSI: KONTEKS HANYA BERISI NAMA SOP (BUKAN RINCIAN PROSEDUR)
# ─────────────────────────────────────────────────────────────

# Penanda bahwa konteks memang berasal dari dokumen berformat formulir SOP
# pemerintah. Dipakai untuk membatasi ruang berlaku penjaga di bawah.
_SOP_FORMAT_MARKERS = ["[Konteks: SOP", "Nomor SOP", "NOMOR SOP", "Nama SOP", "NAMA SOP"]


def _context_is_sop_document(context_text: str) -> bool:
    """
    Apakah konteks ini berasal dari dokumen berformat formulir SOP.

    Penting untuk platform multi-dokumen: penjaga "prosedur tanpa rincian" di
    bawah mengenali rincian lewat nama-nama kolom formulir SOP pemerintah.
    Dokumen di luar format itu — panduan, peraturan, manual — tidak punya kolom
    tersebut, sehingga tanpa pemeriksaan ini SETIAP pertanyaan "bagaimana cara"
    padanya akan ditolak walau jawabannya jelas ada di konteks.
    """
    return any(marker in context_text for marker in _SOP_FORMAT_MARKERS)


def _context_has_full_procedure(context_text: str) -> bool:
    """
    Cek apakah konteks berisi rincian prosedur SOP (Dasar Hukum, Kualifikasi
    Pelaksana, Peralatan/Perlengkapan, langkah-langkah, dsb) — bukan cuma
    daftar nama/judul SOP seperti yang ada di Diktum KEDUA.
    """
    return any(marker in context_text for marker in _SOP_DETAIL_MARKERS)


# ─────────────────────────────────────────────────────────────
# PENJAGA PREMIS PALSU (entitas bernomor yang tidak ada di dokumen)
# ─────────────────────────────────────────────────────────────

# Pertanyaan berpremis palsu adalah kegagalan yang paling berbahaya: jawabannya
# terdengar meyakinkan justru karena modelnya patuh. Ditanya "Diktum KEEMPAT"
# pada keputusan yang hanya punya tiga diktum, model menyodorkan isi Diktum
# KEDUA; ditanya "langkah ke-11" pada prosedur bersepuluh langkah, ia menyalin
# output langkah ke-10. Keduanya bisa dipastikan salah TANPA model, jadi
# diperiksa lebih dulu — pola yang sama dengan penjaga prosedur dan penjaga
# daftar di generate_response.
_URUTAN_DIKTUM = (
    "kesatu", "pertama", "kedua", "ketiga", "keempat", "kelima",
    "keenam", "ketujuh", "kedelapan", "kesembilan", "kesepuluh",
)
_POLA_TANYA_DIKTUM = _re.compile(
    r"\bdiktum\s+(" + "|".join(_URUTAN_DIKTUM) + r")\b", _re.IGNORECASE
)
_POLA_TANYA_LANGKAH = _re.compile(
    r"\b(?:langkah|tahap|tahapan)\s+(?:ke\s*-?\s*)?(\d{1,3})\b", _re.IGNORECASE
)
_POLA_ITEM_BERNOMOR = _re.compile(r"(?m)^\s*(\d{1,3})[.)]\s+\S")

# Di bawah ambang ini konteksnya tidak cukup terstruktur untuk menyimpulkan
# "langkah sebanyak itu tidak ada" — lebih baik diam daripada menolak keliru.
_MIN_ITEM_UNTUK_SIMPULAN = 3


def _nomor_item_tertinggi(context_text: str) -> int:
    """Nomor urut terbesar yang benar-benar ada di konteks, 0 bila tak ada."""
    nomor = [int(m.group(1)) for m in _POLA_ITEM_BERNOMOR.finditer(context_text)]
    return max(nomor) if nomor else 0


def _entitas_tak_ada_di_konteks(query: str, context_text: str) -> str | None:
    """
    Kembalikan nama entitas yang ditanyakan tetapi tidak ada di konteks.

    Hanya menjawab untuk hal yang bisa dipastikan dari teks: nama diktum, dan
    nomor langkah yang melampaui item bernomor tertinggi. Bila konteksnya tidak
    cukup terstruktur, fungsi ini memilih diam — menolak menjawab secara keliru
    jauh lebih merugikan daripada melewatkan satu premis palsu.

    Returns:
        Nama entitas yang tidak ada, atau None bila tidak ada yang bisa
        dipastikan.
    """
    rendah = context_text.lower()

    for m in _POLA_TANYA_DIKTUM.finditer(query):
        nama = m.group(1).lower()
        if "diktum " + nama not in rendah and nama.upper() not in context_text:
            return "Diktum " + nama.upper()

    tertinggi = _nomor_item_tertinggi(context_text)
    if tertinggi >= _MIN_ITEM_UNTUK_SIMPULAN:
        for m in _POLA_TANYA_LANGKAH.finditer(query):
            if int(m.group(1)) > tertinggi:
                return "langkah ke-" + m.group(1)

    return None


def _is_procedure_question(query: str) -> bool:
    """Mendeteksi apakah pertanyaan meminta prosedur/langkah-langkah suatu SOP."""
    query_lower = query.lower()
    return any(k in query_lower for k in _PROCEDURE_QUESTION_KEYWORDS)


# ─────────────────────────────────────────────────────────────
# DAFTAR PANJANG DIEKSTRAK TERPROGRAM (bukan disalin LLM)
# ─────────────────────────────────────────────────────────────
#
# Terukur pada qwen2.5:7b: diminta menyalin daftar 74 item yang SELURUHNYA ada
# di konteks, model berhenti di item ke-46 — tiga kali berturut-turut, di item
# yang persis sama, pada temperature 0. Bukan soal retrieval (74/74 hadir),
# bukan jendela konteks (9.216 dialokasikan, ~6.300 terpakai), bukan batas
# keluaran (num_predict=8192 memberi hasil identik). Menambah instruksi
# "salin seluruhnya" justru MEMPERBURUK: 46 turun jadi 20, karena instruksi
# tambahan ikut berebut perhatian dengan tugas menyalin.
#
# Jadi daftarnya diambil secara terprogram lalu disodorkan ke model — pola yang
# sama seperti _build_comparison_hint di bawah.

# Item daftar: huruf (a. / a) / (a)) atau angka (1. / 1)).
#
# Judul boleh MENYATU di baris yang sama, seperti "Mengingat : 1. Undang-Undang...".
# Bentuk itu lazim pada dokumen resmi dan sempat membuat item pertama tidak
# terdeteksi sama sekali — runtun lalu dimulai dari item KEDUA, dan kata pembeda
# di judulnya ("Mengingat") tertinggal di luar jangkauan penilaian relevansi.
_ENUM_ITEM = _re.compile(
    r"^[ \t]*(?:[^:\n]{0,60}:[ \t]*)?"          # judul opsional di baris yang sama
    r"\(?(?P<tanda>[a-zA-Z]{1,3}|\d{1,3})[.)][ \t]+"
    r"(?P<isi>\S.*?)[ \t]*;?[ \t]*$",
    _re.MULTILINE,
)

# Baris rincian di bawah sebuah item daftar ("- Pelaksana:", "- Waktu: 1 Hari").
# Kehadirannya menandakan daftar BERTINGKAT, yang tidak boleh disajikan sebagai
# daftar datar karena rinciannya justru sering yang ditanyakan.
_ENUM_SUBITEM = _re.compile(r"^[ \t]+[-*•]\s+\S", _re.MULTILINE)

# Batas minimum item agar daftar dijawab terprogram.
#
# Bukan sekadar soal panjang. Model gagal pada dua keadaan: daftar yang terlalu
# panjang untuk disalin utuh, DAN dokumen yang memuat beberapa daftar mirip
# sehingga ia memilih yang keliru — persis yang terjadi pada pertanyaan tentang
# dasar hukum, di mana satu dokumen memuat tiga daftar peraturan sekaligus
# (milik Keputusan, milik SOP Renstra, milik SOP Renja).
#
# Ambang 10 memasukkan keduanya sambil tetap menyisakan daftar sangat pendek
# (mis. "2 SOP yang berkaitan") untuk dijawab model secara wajar.
_ENUM_MIN_ITEMS_FOR_HINT = 10

# Panjang teks pengantar sebelum daftar yang ikut dinilai relevansinya. Di situ
# biasanya tertulis penanda seperti "Dasar Hukum:" atau "KEDUA : ... terdiri dari:"
# yang membedakan satu daftar dari daftar lain di dokumen yang sama.
_ENUM_LEAD_IN = 220

# Kata yang terlalu umum untuk membedakan daftar mana yang dimaksud.
_ENUM_STOPWORDS = {
    "berapa", "total", "yang", "dalam", "dan", "ini", "apa", "saja", "pada",
    "dari", "untuk", "sebutkan", "seluruhnya", "semua", "jumlah", "adalah",
    "dengan", "atau", "itu", "ada", "seluruh", "tercantum", "dibutuhkan",
}


# Kata yang menandakan pengguna meminta daftar UTUH, bukan sekadar beberapa
# contoh. "Sebutkan 5 contoh" tidak butuh daftar 74 item disodorkan.
#
# Dicocokkan di AWAL kata (\b di depan, bebas di belakang): imbuhan akhiran
# harus tetap cocok — "seluruhnya", "semuanya", "lengkapnya" — sementara awalan
# TIDAK boleh, karena "perlengkapan" dan "kelengkapan" memuat "lengkap" tanpa
# ada hubungannya dengan permintaan daftar utuh. Pencocokan substring polos
# membuat pertanyaan "peralatan/perlengkapan apa saja" ikut terjaring.
_COMPLETE_LIST_PATTERN = _re.compile(
    r"\b(?:seluruh|semua|keseluruhan|lengkap|daftar|list|katalog|rincian)"
    r"|\bberapa\s+(?:total|jumlah|banyak)\b",
    _re.IGNORECASE,
)


# Pertanyaan bisa MENYODORKAN jumlah alih-alih memintanya ("benarkah hanya 46
# SOP?"). Bentuk ini tidak tertangkap pola daftar-utuh, sehingga jawabannya
# dulu hanya "lebih dari 46" — premis palsunya memang ditolak, tetapi angka
# sebenarnya tidak pernah disebut. Padahal jumlahnya bisa dihitung pasti.
_POLA_JUMLAH_DISODORKAN = _re.compile(
    r"\b(?:benarkah|betulkah|apakah|benar)\b.{0,90}?\bhanya\b.{0,40}?\b(\d{1,3})\b"
    r"|\bhanya\s+(?:memuat|berisi|ada|terdiri\s+dari)\s+(\d{1,3})\b",
    _re.IGNORECASE | _re.DOTALL,
)


def _jumlah_yang_disodorkan(query: str) -> int | None:
    """Angka yang diklaim pertanyaan sebagai jumlah suatu daftar, bila ada."""
    m = _POLA_JUMLAH_DISODORKAN.search(query)
    if not m:
        return None
    return int(m.group(1) or m.group(2))

def _asks_for_complete_list(query: str) -> bool:
    """Apakah pertanyaan meminta daftar utuh beserta jumlahnya."""
    return bool(_COMPLETE_LIST_PATTERN.search(query))


def _enum_sort_key(marker: str) -> tuple:
    """
    Kunci pengurutan penanda item, supaya "urutan maju" bisa diperiksa.

    Angka memakai nilainya. Huruf memakai (berapa kali diulang, hurufnya):
    a < b < ... < z < aa < bb < ... < zz < aaa. Skema "huruf diulang" itulah
    yang dipakai dokumen resmi Indonesia untuk daftar melebihi 26 item.
    """
    if marker.isdigit():
        return (0, int(marker), "")
    huruf = marker.lower()
    return (1, len(huruf), huruf[0])


def _penanda_huruf_sah(marker: str) -> bool:
    """
    Benar bila penanda huruf memakai skema huruf-diulang (a, aa, aaa, ...).

    Daftar resmi Indonesia yang melebihi 26 item memakai huruf yang diulang,
    bukan gabungan huruf berbeda. Tanpa syarat ini, kata pendek berhuruf besar
    yang kebetulan diikuti titik ikut terbaca sebagai item — nyata terjadi:
    "NIP.196911172001121002" di halaman pengesahan tercatut sebagai item ke-75
    pada daftar yang seharusnya berhenti di 74.

    Konsekuensi yang diterima: angka Romawi (i, ii, iii, iv, v) tidak lagi
    dikenali mulai dari "iv". Skema pengurutan yang ada memang sudah tidak
    menanganinya dengan benar, jadi tidak ada yang hilang.
    """
    return len(set(marker.lower())) == 1

def _penanda_maju(sekarang: str, sebelumnya: str) -> bool:
    """
    Benar bila penanda `sekarang` melanjutkan `sebelumnya`.

    Aturan pokoknya urutan biasa (lihat _enum_sort_key). Yang ditambahkan di
    sini adalah toleransi terhadap kerusakan OCR yang nyata terjadi pada korpus
    ini: halaman hasil pindai kerap kehilangan huruf berulang, sehingga "hhh."
    terbaca "h." dan "jjj." terbaca "jj.".

    Tanpa toleransi itu, penanda yang memendek terbaca sebagai MUNDUR, runtunnya
    terputus di batas halaman, dan daftar 74 item terpecah menjadi 59 + 15 —
    lalu yang 59 menang karena lebih panjang. Kegagalan itu tidak menampakkan
    diri sebagai galat; jawabannya hanya berhenti lebih awal dengan yakin.

    Toleransinya sengaja sempit: hanya bila hurufnya maju TEPAT SATU langkah
    (g -> h). Dua daftar berbeda yang kebetulan bersambung huruf tetap bisa
    salah gabung, tetapi itu jauh lebih jarang daripada OCR yang merontokkan
    huruf pada dokumen pindai.
    """
    kunci_kini, kunci_lalu = _enum_sort_key(sekarang), _enum_sort_key(sebelumnya)
    if kunci_kini > kunci_lalu:
        return True

    # Hanya berlaku antar-penanda huruf.
    if kunci_kini[0] != 1 or kunci_lalu[0] != 1:
        return False

    return ord(kunci_kini[2]) - ord(kunci_lalu[2]) == 1


def _extract_enumeration_runs(
    context_text: str,
) -> list[tuple[list[tuple[str, str]], int, int]]:
    """
    Pecah seluruh item berpenanda menjadi runtun-runtun yang penandanya maju terus.

    Kesinambungan urutan, BUKAN gaya penanda, yang menentukan batas antar daftar.
    Satu konteks kerap memuat beberapa daftar angka yang tak berhubungan — dasar
    hukum, langkah prosedur, peralatan — dan mengelompokkannya berdasarkan gaya
    akan menggabungkan ketiganya menjadi satu daftar palsu.

    Perbandingan memakai "lebih besar", bukan "penerus persis", supaya satu item
    yang terlewat saat OCR tidak memutus runtun.

    Returns:
        List of (daftar item [(penanda, isi)], posisi awal, posisi akhir) dalam
        karakter. Rentang awal–akhir dipakai untuk menilai relevansi: baris
        rincian DI ANTARA item (mis. "- Pelaksana:", "- Waktu:") berada di
        rentang itu, dan kerap justru di situlah kata pembeda pertanyaan berada.
    """
    runs: list[tuple[list[tuple[str, str]], int, int]] = []
    current: list[tuple[str, str]] = []
    previous_key = None
    previous_marker = ""
    start = end = 0

    for match in _ENUM_ITEM.finditer(context_text):
        marker, isi = match.group("tanda"), match.group("isi")
        if not marker.isdigit() and not _penanda_huruf_sah(marker):
            continue
        key = _enum_sort_key(marker)

        # Gaya berganti atau penanda tidak maju -> daftar baru dimulai.
        if previous_key is not None and (
            key[0] != previous_key[0] or not _penanda_maju(marker, previous_marker)
        ):
            runs.append((current, start, end))
            current = []
        if not current:
            # Dijangkar pada PENANDA, bukan awal baris: bila judulnya menyatu
            # ("Mengingat : 1. ..."), judul itu ikut terbaca sebagai teks
            # pengantar saat menilai daftar mana yang dimaksud pertanyaan.
            start = match.start("tanda")

        current.append((marker, isi))
        end = match.end()
        previous_key = key
        previous_marker = marker

    if current:
        runs.append((current, start, end))

    return runs


# Dokumen bisa memuat beberapa bagian berlabel yang isinya nyaris kembar.
# Pada korpus SOP ini, dua SOP berbeda punya daftar peralatan yang sama persis
# di enam butir pertama, dan bagian Kualifikasi yang identik kata per kata
# akibat salin-tempel di dokumen aslinya. Kata pertanyaan tidak membedakan
# keduanya, sehingga pemilihan jatuh ke pemutus terakhir — daftar terpanjang —
# dan pertanyaan tentang yang satu dijawab dengan daftar milik yang lain.
#
# Pembedanya DITURUNKAN dari label yang benar-benar ada di korpus, bukan dari
# daftar nama yang dipatok di kode. Mematoknya berarti layanan ini hanya
# bekerja untuk satu dokumen tertentu, padahal kode yang sama melayani seluruh
# dokumen yang di-ingest.
_POLA_LABEL_KONTEKS = _re.compile(r"\[Konteks:\s*([^\]]+)\]")

# Kata sependek tiga huruf terlalu sering muncul kebetulan untuk dipercaya
# sebagai pembeda; empat huruf menyaringnya tanpa membuang nama yang berarti.
_MIN_HURUF_PEMBEDA = 4


def _label_di_konteks(context_text: str) -> list[str]:
    """Seluruh label [Konteks: ...] yang ada di konteks, unik dan terurut."""
    return sorted({m.group(1).strip() for m in _POLA_LABEL_KONTEKS.finditer(context_text)})


def _kata_pembeda_label(labels: list[str]) -> dict:
    """
    Kata yang HANYA dimiliki satu label di antara label-label yang ada.

    Inilah yang menggantikan daftar nama yang dulu dipatok di kode. Kata yang
    dipakai bersama semua label ("sop", "penyusunan", "rencana") tidak
    membedakan apa pun dan otomatis gugur; yang tersisa justru kata penentu
    seperti nama khas tiap bagian. Berlaku untuk dokumen apa pun, karena
    daftarnya lahir dari isi korpus itu sendiri.

    Returns:
        Peta label -> himpunan kata pembedanya. Bisa kosong bila dua label
        kebetulan memakai kata yang sama semua.
    """
    kata = {
        label: set(_re.findall(rf"[a-z0-9]{{{_MIN_HURUF_PEMBEDA},}}", label.lower()))
        for label in labels
    }
    return {
        label: milik - set().union(*(lain for l, lain in kata.items() if l != label))
        if len(kata) > 1 else milik
        for label, milik in kata.items()
    }


def _label_yang_ditanya(query: str, labels: list[str]) -> list[str]:
    """Label mana yang disebut pertanyaan, dilihat dari kata pembedanya."""
    rendah = query.lower()
    pembeda = _kata_pembeda_label(labels)
    return [l for l in labels if any(k in rendah for k in pembeda[l])]

def _label_yang_menaungi(context_text: str, posisi: int) -> str:
    """Label [Konteks: ...] terdekat SEBELUM posisi, atau string kosong."""
    terakhir = ""
    for m in _POLA_LABEL_KONTEKS.finditer(context_text, 0, posisi):
        terakhir = m.group(1)
    return terakhir


def _saring_menurut_label(kandidat, context_text, query):
    """
    Buang runtun yang berada di bawah label yang jelas bukan yang ditanya.

    Hanya aktif bila pertanyaan menyebut TEPAT SATU label. Pertanyaan
    pembanding menyebut lebih dari satu dan justru MEMBUTUHKAN semuanya tetap
    ada; menyaringnya akan merusak jawaban yang selama ini sudah benar. Runtun
    tanpa label di atasnya tidak pernah dibuang, sebab ketiadaan label bukan
    bukti ketidakcocokan.
    """
    if _is_list_query(query):
        return kandidat

    labels = _label_di_konteks(context_text)
    if len(labels) < 2:
        return kandidat            # tak ada yang bisa tertukar

    diminta = _label_yang_ditanya(query, labels)
    if len(diminta) != 1:
        return kandidat
    sasaran = diminta[0]

    tersisa = []
    for run, awal, akhir in kandidat:
        naungan = _label_yang_menaungi(context_text, awal).strip()
        if not naungan or naungan == sasaran:
            tersisa.append((run, awal, akhir))

    # Bila penyaringan menghabiskan semua calon, penyaringannya yang keliru.
    if not tersisa:
        return kandidat
    if len(tersisa) < len(kandidat):
        logger.info(
            "Saring label: %d dari %d runtun dibuang (pertanyaan tentang %s)",
            len(kandidat) - len(tersisa), len(kandidat), sasaran[:60],
        )
    return tersisa

def _select_relevant_run(
    runs: list[tuple[list[tuple[str, str]], int, int]],
    context_text: str,
    query: str,
) -> list[tuple[str, str]] | None:
    """
    Pilih runtun yang paling cocok dengan pertanyaan.

    Runtun terpanjang bukan jawabannya: satu dokumen bisa memuat daftar SOP 74
    item DAN daftar dasar hukum 13 item, dan pertanyaan tentang dasar hukum
    harus mendapat yang kedua. Penilaian memakai kata dari pertanyaan yang
    ditemukan di teks pengantar daftar plus beberapa item pertamanya.
    """
    # Seluruh runtun ikut dinilai, TERMASUK yang pendek. Menyaring yang panjang
    # lebih dulu adalah kesalahan: daftar terpanjang lalu menang tanpa lawan,
    # sehingga pertanyaan tentang dasar hukum (13 item) pun mendapat daftar SOP
    # 74 item hanya karena daftar pendeknya sudah tersingkir dari pencalonan.
    kandidat = [(r, a, b) for r, a, b in runs if len(r) >= 5]
    if not kandidat:
        return None

    if _is_list_query(query):
        # Untuk query katalog/daftar seluruh SOP, utamakan runtun daftar terpanjang (master katalog 74 SOP)
        kandidat.sort(key=lambda x: len(x[0]), reverse=True)
        return kandidat[0][0]

    kandidat = _saring_menurut_label(kandidat, context_text, query)

    kata = {
        w for w in _re.findall(r"\w+", query.lower())
        if len(w) > 2 and w not in _ENUM_STOPWORDS
    }
    if not kata:
        return None

    # Dinilai atas teks pengantar DAN seluruh rentang daftarnya. Membatasi
    # penilaian pada judul item saja membuat pertanyaan tentang rincian
    # ("siapa pelaksananya", "berapa waktunya") kehilangan kata pembedanya,
    # karena kata itu ada di baris rincian di antara item.
    ladang = [
        (context_text[max(0, awal - _ENUM_LEAD_IN):akhir]).lower()
        for _, awal, akhir in kandidat
    ]

    # Kata dibobot menurut KELANGKAAN di antara kandidat. Menghitung tiap kata
    # sama berat membuat kata umum menenggelamkan kata penentu: "sop", "dasar",
    # dan "hukum" muncul di hampir semua daftar sehingga tidak membedakan apa
    # pun, sedangkan "Mengingat" — yang hanya ada di satu daftar — justru
    # kalah suara meski ialah satu-satunya pembeda yang sesungguhnya.
    bobot = {}
    for w in kata:
        muncul = sum(1 for l in ladang if w in l)
        bobot[w] = 1.0 / muncul if muncul else 0.0

    skor = [
        (sum(bobot[w] for w in kata if w in l), len(run), run)
        for l, (run, _, _) in zip(ladang, kandidat)
    ]

    skor.sort(key=lambda x: (-x[0], -x[1]))
    terbaik = skor[0]

    # Tanpa satu pun kata pertanyaan yang cocok, tidak ada dasar untuk memilih.
    if terbaik[0] <= 0:
        return None
    # Daftar pendek disalin model dengan andal — membantu di situ hanya menambah
    # panjang konteks tanpa manfaat, dan berisiko mengganggu jawaban yang sudah benar.
    if terbaik[1] < _ENUM_MIN_ITEMS_FOR_HINT:
        return None

    return terbaik[2]


def _build_enumeration_answer(context_text: str, query: str) -> str | None:
    """
    Susun jawaban daftar lengkap secara terprogram, tanpa melibatkan LLM sama sekali.

    Menyisipkan daftar ke dalam konteks lalu meminta model menyalinnya sudah
    dicoba dan GAGAL: jawaban justru memburuk dari 46 item menjadi 31, dan
    jumlah yang disebut dari 46 menjadi 26. Menambah teks ke konteks membuat
    model makin buruk, bukan makin baik — sama seperti menambah instruksi.

    Jadi untuk kasus sempit ini — pertanyaan meminta daftar utuh, dan dokumen
    memuat daftar panjang yang relevan — daftarnya dikirim apa adanya. Pola yang
    sama sudah dipakai dua penjaga lain di generate_response: bila jawabannya
    bisa dipastikan tanpa model, jangan libatkan model.

    Returns:
        Teks jawaban siap kirim, atau None bila kasusnya tidak berlaku.
    """
    disodorkan = _jumlah_yang_disodorkan(query)
    minta_daftar_utuh = _is_list_query(query) and _asks_for_complete_list(query)
    if not minta_daftar_utuh and disodorkan is None:
        return None

    runs = _extract_enumeration_runs(context_text)
    run = _select_relevant_run(runs, context_text, query)
    if run is None:
        return None

    awal, akhir = next(((a, b) for r, a, b in runs if r is run), (0, 0))

    # Daftar yang tiap itemnya punya baris rincian sendiri — "- Pelaksana:",
    # "- Waktu:", "- Output:" — TIDAK boleh dijawab sebagai daftar datar:
    # jawabannya akan kehilangan justru bagian yang ditanyakan. Serahkan ke LLM.
    if _ENUM_SUBITEM.search(context_text[awal:akhir]):
        logger.info("Daftar terpilih memuat rincian bertingkat — diserahkan ke LLM")
        return None

    # Kalimat pengantar diambil dari dokumen (teks tepat sebelum daftarnya),
    # bukan dikarang — di situ biasanya tertulis daftar apa ini.
    pengantar = context_text[max(0, awal - _ENUM_LEAD_IN):awal]
    pengantar = _re.sub(r"\[[^\]]*\]", " ", pengantar)          # buang penanda [Halaman N] dsb
    pengantar = " ".join(pengantar.split())[-160:].strip()
    # Mulai dari batas kalimat supaya tidak terpotong di tengah kata.
    potong = _re.search(r"[.:;]\s+(\S.*)$", pengantar)
    if potong:
        pengantar = potong.group(1)

    # Sebutkan daftar ini milik SOP yang mana. Jawaban terprogram tidak melalui
    # LLM, jadi tidak ada tahap yang bisa menyadari salah ambil; menyebut
    # sumbernya membuat kekeliruan semacam itu langsung kelihatan oleh pembaca.
    label = _label_yang_menaungi(context_text, awal)
    if label and label.lower() in ("mengingat", "menimbang", "memutuskan", "menetapkan", "kedua", "kesatu"):
        label = ""
    asal = f" ({label})" if label else ""

    baris = [f"Terdapat **{len(run)}** item{asal}. Berikut daftar lengkapnya:"]
    if len(pengantar) > 20:
        baris = [f"{pengantar}", "", f"Terdapat **{len(run)}** item{asal} selengkapnya:"]

    # Bantahan didahulukan supaya pembaca tidak perlu menghitung sendiri untuk
    # tahu bahwa angka di pertanyaannya keliru. Disisipkan SESUDAH pengantar
    # dirakit, sebab perakitan itu menimpa seluruh isi baris.
    if disodorkan is not None and disodorkan != len(run):
        baris[:0] = [f"Tidak benar. Jumlah yang tercantum bukan {disodorkan}.", ""]
    baris.append("")
    baris += [f"{n}. {isi}" for n, (_, isi) in enumerate(run, 1)]

    logger.info(
        "Daftar %d item dijawab terprogram tanpa LLM (pertanyaan meminta daftar utuh)",
        len(run),
    )
    return "\n".join(baris)


# ─────────────────────────────────────────────────────────────
# TABEL PERBANDINGAN TERSTRUKTUR (untuk pertanyaan comparison)
# ─────────────────────────────────────────────────────────────

def _extract_list_items(block: str, field_name: str) -> list[str]:
    """Ekstrak daftar item dari sebuah field (misal Peralatan/Perlengkapan) dalam teks blok SOP."""
    escaped = _re.escape(field_name).replace(r"\/", r"[\/\s]+")
    pattern = _re.compile(
        rf"[-*]?\s*\*{{0,2}}{escaped}\*{{0,2}}:\s*(?:[ \t]*\n)?(.*?)(?=\n\s*[-*]?\s*\*{{0,2}}[A-Z][a-zA-Z /]+:\s*|\n\s*---|\n\s*\[|\Z)",
        _re.IGNORECASE | _re.DOTALL
    )
    match = pattern.search(block)
    if not match:
        return []
    raw = match.group(1)
    items = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-*0123456789. ").rstrip(",;").strip()
        line = _re.sub(r"\*+", "", line).strip()
        if line:
            items.append(line)
    return items


def _build_comparison_hint(context_text: str, query: str) -> str:
    """
    Jika query adalah pertanyaan perbandingan antara dua SOP,
    bangun tabel perbandingan terstruktur dari context_text dan sisipkan di awal.
    Ini membantu LLM lokal yang lemah dalam reasoning perbandingan.

    PENTING: Pengelompokan blok dilakukan berdasarkan tag [Konteks: NAMA SOP]
    yang sudah tertanam di dalam teks chunk sejak proses ingestion — BUKAN
    berdasarkan document_id, karena beberapa SOP berbeda bisa berasal dari
    document_id yang sama (satu PDF berisi banyak SOP).
    """
    query_lower = query.lower()
    is_comparison = any(k in query_lower for k in [
        "perbedaan", "berbeda", "beda", "dibanding", "antara", "vs",
        "tidak dibutuhkan", "hanya ada di", "tidak ada di", "khusus",
    ])
    if not is_comparison:
        return context_text

    blocks = _re.split(r"\n---\n", context_text)
    sop_blocks: dict[str, str] = {}
    for block in blocks:
        match = _re.search(r"\[Konteks:\s*(.+?)\]", block)
        if match:
            sop_name = match.group(1).strip()
            if sop_name not in sop_blocks:
                sop_blocks[sop_name] = block
            else:
                # Gabungkan blok tambahan dari SOP yang sama (misal beda halaman)
                sop_blocks[sop_name] += "\n" + block

    if len(sop_blocks) < 2:
        return context_text

    FIELDS_TO_COMPARE = [
        "Peralatan/Perlengkapan", "Kualifikasi Pelaksana", "Keterkaitan",
        "Dasar Hukum", "Peringatan"
    ]

    sop_names = list(sop_blocks.keys())
    sop_a_name, sop_b_name = sop_names[0], sop_names[1]
    sop_a_text, sop_b_text = sop_blocks[sop_a_name], sop_blocks[sop_b_name]

    hint_lines = [
        "=== TABEL PERBANDINGAN TERSTRUKTUR (WAJIB DIGUNAKAN SEBAGAI ACUAN UTAMA JAWABAN) ===",
        "Instruksi Khusus Analisis Perbandingan:",
        "- Sebutkan secara jelas apa saja item yang SAMA di kedua SOP.",
        "- Sebutkan secara eksplisit dan rinci apa saja item yang HANYA ADA di SOP A dan apa saja yang HANYA ADA di SOP B berdasarkan rincian berikut:",
        f"SOP A: {sop_a_name}",
        f"SOP B: {sop_b_name}",
    ]

    for field in FIELDS_TO_COMPARE:
        items_a = _extract_list_items(sop_a_text, field)
        items_b = _extract_list_items(sop_b_text, field)
        if not items_a and not items_b:
            continue

        norm_b = {x.lower(): x for x in items_b}
        norm_a = {x.lower(): x for x in items_a}

        in_both = [x for x in items_a if x.lower() in norm_b]
        only_in_a = [x for x in items_a if x.lower() not in norm_b]
        only_in_b = [x for x in items_b if x.lower() not in norm_a]

        if in_both or only_in_a or only_in_b:
            hint_lines.append(f"\n[PERBANDINGAN: {field}]")
            if in_both:
                hint_lines.append(f"  SAMA di kedua SOP ({len(in_both)} item): {'; '.join(in_both)}")
            if only_in_a:
                hint_lines.append(f"  HANYA di {sop_a_name} ({len(only_in_a)} item): {'; '.join(only_in_a)}")
            if only_in_b:
                hint_lines.append(f"  HANYA di {sop_b_name} ({len(only_in_b)} item): {'; '.join(only_in_b)}")

    hint_lines.append("=== AKHIR TABEL PERBANDINGAN ===\n")
    hint_text = "\n".join(hint_lines)
    return hint_text + "\n\n---\n\n" + context_text


def _build_time_calculation_hint(context_text: str, query: str) -> str:
    """
    Kalkulator Terprogram: Melakukan perhitungan durasi absolut dari konteks SOP, 
    lalu merangkumnya menjadi instruksi matematis pasti untuk LLM.
    """
    from app.services import tool_router
    import re

    blocks = re.split(r"\n---\n", context_text)
    sop_blocks: dict[str, str] = {}
    for block in blocks:
        match = re.search(r"\[Konteks:\s*(.+?)\]", block)
        if match:
            sop_name = match.group(1).strip()
            if sop_name not in sop_blocks:
                sop_blocks[sop_name] = block
            else:
                sop_blocks[sop_name] += "\n" + block
        else:
            if "Umum" not in sop_blocks:
                sop_blocks["Umum"] = block
            else:
                sop_blocks["Umum"] += "\n" + block

    hint_lines = [
        "=== [DATA PERHITUNGAN WAKTU OTOMATIS] ===",
        "Sistem telah menghitung total waktu prosedural secara matematis mutlak per dokumen:",
    ]

    found_time = False
    for sop_name, text_block in sop_blocks.items():
        calc_result = tool_router.parse_and_sum_durations_from_context(text_block)
        if calc_result:
            total_hari = calc_result.get("total_hari", 0)
            formatted_total = calc_result.get("formatted_total", "")
            kalender_info = ""

            if total_hari > 0:
                hari_kerja_bulat = int(total_hari) if total_hari.is_integer() else int(total_hari)
                est = tool_router.hitung_estimasi_selesai(hari_kerja_bulat)
                tgl_selesai = est.get("tanggal_selesai", "")
                if tgl_selesai:
                    kalender_info = f" (Estimasi selesai jika dimulai hari ini: {tgl_selesai} - potong libur akhir pekan)"

            if formatted_total:
                hint_lines.append(f"- Waktu SOP {sop_name}: {formatted_total}{kalender_info}")
                found_time = True

    if not found_time:
        return context_text

    hint_lines.extend([
        "",
        "TUGAS SANGAT KETAT UNTUK AI:",
        "1. Pilih HANYA SATU waktu SOP dari daftar di atas yang paling relevan dengan pertanyaan pengguna (misal: jika ditanya Renja, pilih Renja saja).",
        "2. DILARANG KERAS menjumlahkan waktu dari dua SOP yang berbeda (Jangan menjawab 50 hari jika ada 2 SOP yang masing-masing 25 hari!).",
        "3. DILARANG KERAS membuat daftar bernomor (1, 2, 3...) yang berisi rincian tahapan.",
        "4. FORMAT JAWABAN WAJIB: 'Berdasarkan SOP [Nama SOP yang dipilih], total waktu yang dibutuhkan adalah [Total Waktu]. [Estimasi Selesai]'",
        "=========================================\n"
    ])
    
    hint_text = "\n".join(hint_lines)
    return context_text + "\n\n---\n\n" + hint_text

# ─────────────────────────────────────────────────────────────
# KEYWORD EXTRACTION & DETEKSI TIPE QUERY
# ─────────────────────────────────────────────────────────────

def _petunjuk_fokus_label(query: str, context_text: str) -> str:
    """
    Susun peringatan singkat bila konteks memuat lebih dari satu bagian berlabel.

    Konteks yang dikirim ke LLM kerap memuat dua bagian sekaligus yang isinya
    nyaris kembar. Model diberi kesempatan mencampur, lalu memang mencampur:
    pernah menjawab bahwa satu SOP berkaitan dengan SOP lain — padahal itu
    milik tetangganya — sambil mengarang rujukan halaman.

    Menyaring konteksnya sengaja TIDAK dilakukan: pertanyaan pembanding
    membutuhkan seluruh bagian tetap ada, dan empat pertanyaan semacam itu
    sudah terjawab benar. Yang ditambahkan hanya petunjuk, sehingga kasus
    terburuk dari salah deteksi cuma satu kalimat mubazir.

    Returns:
        Kalimat petunjuk, atau string kosong bila tidak berlaku.
    """
    labels = _label_di_konteks(context_text)
    if len(labels) < 2:
        return ""

    diminta = _label_yang_ditanya(query, labels)
    if len(diminta) != 1:
        return ""

    sasaran = diminta[0]
    lain = [l for l in labels if l != sasaran]
    return (
        "\n\nPENTING: Pertanyaan ini HANYA tentang " + sasaran + ". "
        "Konteks di atas juga memuat " + ", ".join(lain) + " yang isinya "
        "nyaris sama. Ambil jawaban HANYA dari bagian yang berlabel "
        + sasaran + "; jangan memakai data dari bagian yang lain."
    )



def _is_list_query(query: str) -> bool:
    """
    Mendeteksi apakah pertanyaan pengguna meminta katalog/daftar panjang seluruh SOP
    (misal: 'daftar seluruh SOP', 'sebutkan semua SOP di diktum kedua', 'ada berapa SOP').
    JANGAN mencocokkan pertanyaan spesifik seperti 'apa saja syarat...', 'apa saja berkas...', atau detail di dalam suatu SOP.
    """
    query_lower = query.lower()

    # Pengecualian: jika menanyakan rincian spesifik di dalam suatu SOP (syarat, langkah, perlengkapan, durasi, dll.)
    specific_exclusions = [
        "syarat", "persyaratan", "langkah", "tahapan", "perlengkapan", "output", "hasil",
        "waktu", "durasi", "lama", "biaya", "pelaksana", "penanggung jawab", "dasar hukum",
    ]
    if any(ex in query_lower for ex in specific_exclusions):
        if not any(k in query_lower for k in ["seluruh sop", "semua sop", "total sop", "ada berapa sop", "katalog sop"]):
            return False

    global_list_triggers = [
        "daftar seluruh sop", "daftar semua sop", "daftar sop yang ada", "daftar sop diskominfotik",
        "semua sop", "seluruh sop", "macam-macam sop", "jenis-jenis sop", "list sop", "diktum kedua",
        "ada berapa sop", "total sop", "katalog sop", "apa saja sop yang ada", "apa saja sop di"
    ]
    return any(k in query_lower for k in global_list_triggers)
