"""
Service RAG (Retrieval-Augmented Generation).
Melakukan pencarian konteks di ChromaDB dan menghasilkan jawaban
menggunakan LLM Ollama secara streaming.
"""

import logging
import math
import re
import threading
_re = re
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import settings
from app.database import get_chatbot_rag_config, get_document_names_by_ids
from app.services import session_memory, tool_router
from app.services.embedding_service import (
    encode_query,
    encode_texts,
    get_chroma_collection,
    get_embedding_model,
    get_reranker_model,
    read_corpus_version,
)

logger = logging.getLogger(__name__)

_bm25_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────

# Jumlah dokumen konteks yang diambil per query oleh vector store
_TOP_K = 8

# Jumlah chunk maksimum yang dikirim ke LLM setelah multi-query aggregation.
_MAX_CONTEXT_CHUNKS = 10

# Limit lebih longgar khusus untuk query bertipe daftar/list lengkap
_MAX_CONTEXT_CHUNKS_LIST_QUERY = 20

# ── Jendela konteks LLM ──────────────────────────────────────
#
# num_ctx DIPATOK ke settings.LLM_NUM_CTX (lihat config.py), tidak lagi dihitung
# per pertanyaan. Setiap nilai num_ctx berbeda memaksa Ollama memuat ulang
# llama-server dari nol (~23 detik); num_ctx dinamis membuat tiap pertanyaan
# dengan panjang konteks berbeda membayar reload itu.
#
# Konstanta di bawah kini hanya dipakai untuk MENAKSIR jumlah token konteks yang
# ditampilkan di telemetri (_estimasi_token_konteks) — bukan untuk menentukan
# jendela.

# Perkiraan kasar karakter per token untuk teks bahasa Indonesia. Sengaja
# konservatif (kecil) supaya taksirannya melebihkan, bukan mengurangi.
_CHARS_PER_TOKEN = 3.0

# Ruang yang disisakan untuk jawaban model (dipakai di taksiran telemetri).
_NUM_CTX_RESPONSE_HEADROOM = 2048

# Jendela cadangan bila alokasi pada LLM_NUM_CTX gagal (OOM) sebelum satu potong
# jawaban pun terkirim — dicoba sekali, lalu galat dinaikkan apa adanya.
_NUM_CTX_FALLBACK = 4096

# Konstanta k untuk Reciprocal Rank Fusion (RRF).
# Nilai standar di literatur information retrieval adalah 60.
_RRF_K = 60

# Ambang batas skor BM25 minimum agar sebuah chunk dianggap "match" secara leksikal.
_BM25_MIN_SCORE = 0.1

# Timeout (detik) untuk request ke Ollama. Dinaikkan karena inferensi di CPU bisa lambat.
_OLLAMA_TIMEOUT = 300

# Berapa lama model tetap "warm" (di-load) di memori Ollama antar-request.
# Mencegah reload model dari disk setiap kali dipanggil, yang bisa memicu timeout.
_OLLAMA_KEEP_ALIVE = "30m"

# Jumlah layer yang dipaksa ke GPU (lihat LLM_NUM_GPU di config.py untuk
# alasan dan prasyaratnya). None = serahkan ke auto-fit Ollama.
#
# Sama seperti num_ctx, nilai ini WAJIB seragam di setiap panggilan ke model
# teks: Ollama memuat ulang llama-server dari nol setiap kali salah satunya
# berubah.
_NUM_GPU = settings.LLM_NUM_GPU or None

# Field yang menandakan sebuah chunk berisi RINCIAN prosedur SOP (bukan cuma daftar nama).
_SOP_DETAIL_MARKERS = [
    "Dasar Hukum:", "Kualifikasi Pelaksana:", "Peralatan/Perlengkapan:",
    "Pelaksana:", "Kelengkapan:",
]

# Kata kunci yang menandakan pertanyaan meminta prosedur/langkah-langkah
_PROCEDURE_QUESTION_KEYWORDS = ["prosedur", "langkah", "bagaimana cara", "tahapan", "tata cara"]

# Kamus pemetaan akronim kedinasan ke nama resmi SOP untuk ekspansi query & reranker
_ACRONYM_EXPANSIONS = {
    "renja": "Penyusunan Rencana Kerja (Renja)",
    "renstra": "Penyusunan Rencana Strategis (Renstra)",
    "rka": "Penyusunan Rencana Kegiatan Anggaran (RKA)",
    "lkjip": "Penyusunan Laporan Kinerja Instansi Pemerintah (LKjIP)",
    "lppd": "Penyiapan dan Kompilasi Data Capaian Kinerja Penyelenggaraan Pemerintah Daerah (LPPD)",
    "pk": "Penyusunan Perjanjian Kinerja (PK)",
    "dpa": "Dokumen Pelaksanaan Anggaran (DPA)",
    "iku": "Indikator Kinerja Utama (IKU)",
    "sakip": "Sistem Akuntabilitas Kinerja Instansi Pemerintah (SAKIP)",
    "csirt": "Penanganan Insiden Siber CSIRT",
    "smart city": "Smart City",
}

from datetime import datetime

# Daftar nama hari dan bulan dalam Bahasa Indonesia untuk konteks waktu dinamis
_NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
_NAMA_BULAN = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


_RE_DOUBT_OR_CORRECTION = re.compile(
    r"\b(salah|keliru|bukan|bukannya|kok beda|kok salah|kok bisa|kenapa beda|memang iya|masa sih|yakin|beneran|serius|ngaco|bohong|ngibul|gak bener|tidak benar|kurang tepat|tidak tepat|hitung kembali|hitung ulang)\b",
    re.IGNORECASE,
)


def _is_doubt_or_correction_query(text: str) -> bool:
    """Mendeteksi apakah pertanyaan pengguna adalah bentuk keraguan, sanggahan, atau koreksi jawaban sebelumnya."""
    if not text:
        return False
    return bool(_RE_DOUBT_OR_CORRECTION.search(text))


def _get_current_date_info() -> str:
    """Mengembalikan teks hari dan tanggal saat ini dalam Bahasa Indonesia."""
    now = datetime.now()
    hari = _NAMA_HARI[now.weekday()]
    bulan = _NAMA_BULAN[now.month]
    return f"{hari}, {now.day} {bulan} {now.year}"


def _get_institution_info() -> str:
    """Mengambil ringkasan profil instansi terkini secara dinamis dari basis data atau fallback standar."""
    try:
        from app.database import get_active_fast_paths
        fast_paths = get_active_fast_paths()
        kadis_info = "Ir. Muhammad Zubir, S.Si.T, M.Si. (resmi menjabat sejak 20 April 2026)"
        alamat_info = "Balai Kota Banda Aceh (Gedung C Lantai 3), Jl. Tgk. Abu Lam U No. 7, Banda Aceh"
        kontak_info = "diskominfotik@bandaacehkota.go.id | Call Center Darurat: 112"
        for fp in fast_paths:
            title = (fp.get("title") or "").lower()
            resp = (fp.get("response_text") or "").replace("\n", " ").strip()
            if "kepala dinas" in title or "profil" in title:
                kadis_info = resp
            elif "alamat" in title or "lokasi" in title:
                alamat_info = resp
            elif "kontak" in title or "website" in title:
                kontak_info = resp

        return (
            "- Instansi: Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh\n"
            f"- Kepala Dinas Saat Ini (Pejabat Aktif): {kadis_info}\n"
            f"- Alamat Kantor: {alamat_info}\n"
            f"- Kontak Layanan: {kontak_info}"
        )
    except Exception as e:
        logger.warning("Gagal mengambil dynamic institution info: %s", e)
        return (
            "- Instansi: Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh\n"
            "- Kepala Dinas Saat Ini (Pejabat Aktif): Ir. Muhammad Zubir, S.Si.T, M.Si. (resmi menjabat sejak 20 April 2026)\n"
            "- Alamat Kantor: Balai Kota Banda Aceh (Gedung C Lantai 3), Jl. Tgk. Abu Lam U No. 7, Banda Aceh\n"
            "- Kontak Layanan: diskominfotik@bandaacehkota.go.id | Call Center Darurat: 112"
        )


# System prompt standar untuk LLM bila belum diubah di pengaturan admin
_SYSTEM_PROMPT = """Anda adalah Petugas Layanan Informasi dan Helpdesk resmi Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh. Tugas Anda adalah memberikan jawaban yang akurat, ramah, solutif, ringkas, dan profesional kepada masyarakat dan ASN berdasarkan dokumen resmi yang disediakan.

Waktu Acuan:
- Hari & Tanggal Hari Ini: {current_date}

Profil Instansi Terkini:
{institution_info}

Konteks Dokumen Resmi:
{context}

Pedoman Komunikasi & Inferensi:
1. Kepatuhan Fakta & Anti-Halusinasi:
   - Jawab HANYA berdasarkan fakta yang tertulis pada "Konteks Dokumen Resmi" atau "Profil Instansi Terkini". JANGAN mengarang nama pejabat, tanggal, regulasi, nomor kontak, atau prosedur di luar data tersebut.
   - DILARANG mengarang kepanjangan singkatan/akronim (misal: SPPD, SPT, Renja, RKA, dsb) jika tidak tertulis di teks dokumen. Tulis singkatannya apa adanya.

2. Aturan Pembedaan Pejabat Dokumen vs Pejabat Aktif:
   - Pertanyaan Dokumen/SOP: Bila pengguna menanyakan siapa pejabat/pimpinan yang mengesahkan atau tertulis "di dalam SOP/dokumen", salin PERSIS nama pejabat dan NIP yang tertera pada lembar identitas/pengesahan dokumen SOP pada Konteks Dokumen.
   - Pertanyaan Kondisi Saat Ini: Bila pengguna menanyakan siapa pimpinan/Kepala Dinas "saat ini / sekarang / pejabat aktif", gunakan data pimpinan pada "Profil Instansi Terkini".

3. Gaya Jawaban Alami, Ringkas & Anti-Repetisi:
   - Jawablah secara to-the-point, santun, dan natural layaknya petugas helpdesk yang responsif.
   - HINDARI pengulangan (repetisi): Jika rincian langkah atau prosedur sudah pernah dijabarkan pada pesan sebelumnya di riwayat percakapan, JANGAN mengulang menulis kembali seluruh daftar langkah tersebut. Cukup berikan ringkasan atau kesimpulan inti dari hal yang ditanyakan.
   - HINDARI membuat tabel panjang yang memakan ruang kecuali jika pengguna secara eksplisit meminta format tabel.
   - Hanya ucapkan salam pembuka jika pengguna mengawali pesan dengan salam. JANGAN menggunakan emoji atau simbol grafis berlebihan.

4. Prosedur & Persyaratan SOP:
   - HANYA sajikan rincian poin langkah (1, 2, 3...) JIKA pengguna secara spesifik menanyakan "bagaimana alur/prosedur/cara".
   - JIKA pengguna HANYA menanyakan estimasi waktu, JANGAN sebutkan poin tahapan langkahnya sama sekali.
   - Rujuk bagian 'Kelengkapan', 'Persyaratan', atau 'Kualifikasi Pelaksana' bila ditanyakan syarat permohonan.

5. Estimasi Waktu & Kalkulasi Kalender:
   - Bila terdapat blok [DATA PERHITUNGAN WAKTU OTOMATIS] pada Konteks Dokumen, GUNAKAN angka mutlak dan tanggal selesai dari data tersebut. JANGAN menghitung jumlah hari atau memprediksi tanggal kalender sendiri.
   - Sampaikan estimasi waktu selesai kepada pengguna secara ringkas, lugas, dan natural dalam 1–2 kalimat (contoh: "Total pengerjaan adalah 25 Hari Kerja. Jika dimulai hari ini, maka diperkirakan selesai pada tanggal 30 Oktober 2026").
   - JANGAN membuat simulasi rincian kalender per hari yang panjang.

6. Analisis Perbandingan & Komparasi Antar-SOP:
   - Bila pengguna menanyakan perbandingan (misal: perbedaan peralatan, syarat, waktu, kualifikasi, atau keterkaitan antara dua SOP), lakukan perbandingan langsung terhadap data masing-masing SOP yang tercantum pada Konteks Dokumen Resmi (atau gunakan Tabel Perbandingan Terstruktur bila disediakan).
   - Jelaskan secara terstruktur: persamaan di antara keduanya, apa yang hanya ada di SOP pertama, dan apa yang hanya ada di SOP kedua. JANGAN menyatakan informasi tidak ditemukan jika rincian masing-masing SOP sudah ada di konteks.

7. Penulisan Sumber Referensi:
   - DILARANG KERAS merangkai atau mengetik blok "**Sumber Referensi:**" di akhir kalimat Anda.
   - Sistem akan menyisipkan sumber referensi secara otomatis, jadi Anda cukup fokus pada isi jawaban saja.

8. Penyebutan Daftar Spesifik (Peralatan, Persyaratan, Dasar Hukum):
   - JIKA ditanya "peralatan" atau "perlengkapan", cari bagian khusus berjudul "Peralatan/Perlengkapan" (berisi Komputer, Printer, ATK, dll) dan sebutkan SELURUH daftarnya tanpa diringkas atau dikurangi.
   - BEDA ISTILAH: "Peralatan/Perlengkapan" adalah alat kerja utama SOP. Sedangkan "Kelengkapan" di dalam tabel adalah dokumen masukan untuk tiap tahapan. DILARANG tertukar antara keduanya!
   - Selalu gunakan format daftar nomor/peluru bila menyebutkan daftar, JANGAN meringkasnya menjadi satu kalimat.

9. Isolasi Entitas & Anti-Pencampuran (Entity Disambiguation):
   - JIKA konteks berisi potongan dari beberapa dokumen/SOP yang mirip (contoh: Renja dan Renstra), BACA DENGAN TELITI judul dokumen mana yang sedang ditanyakan pengguna.
   - JANGAN PERNAH mencampuradukkan daftar peralatan, syarat, atau waktu dari SOP A ke SOP B. 
   - Pastikan Anda HANYA mengekstrak data dari potongan teks yang membahas entitas/SOP yang secara spesifik ditanyakan pengguna."""


def _format_pages_list(pages: list[int]) -> str:
    """
    Format daftar nomor halaman integer menjadi string rentang atau koma yang rapi.
    Contoh: [3, 4, 5, 6] -> 'Halaman 3–6', [64, 65] -> 'Halaman 64, 65'.
    """
    if not pages:
        return ""
    sorted_pages = sorted(set(pages))
    ranges: list[str] = []
    start = sorted_pages[0]
    prev = sorted_pages[0]

    for p in sorted_pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            if start == prev:
                ranges.append(str(start))
            elif prev == start + 1:
                ranges.append(f"{start}, {prev}")
            else:
                ranges.append(f"{start}-{prev}")
            start = p
            prev = p

    if start == prev:
        ranges.append(str(start))
    elif prev == start + 1:
        ranges.append(f"{start}, {prev}")
    else:
        ranges.append(f"{start}-{prev}")

    return f"Halaman {', '.join(ranges)}"


# ─────────────────────────────────────────────────────────────
# HYBRID RETRIEVAL (Vector + BM25, digabung via Reciprocal Rank Fusion)
# ─────────────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    vector_ranked_ids: list[str],
    bm25_ranked_ids: list[str],
    k: int = _RRF_K,
) -> dict[str, float]:
    """
    Menggabungkan dua daftar hasil retrieval (vector search & BM25) menggunakan
    Reciprocal Rank Fusion (RRF).

    RRF menggabungkan berdasarkan PERINGKAT (rank), bukan skor mentah — sehingga
    tidak ada masalah "skala skor tidak sepadan" seperti pendekatan hardcode
    distance BM25 = 0.001 (yang membuat BM25 selalu menang atas vector search
    meski relevansinya lemah).

    Args:
        vector_ranked_ids: List id chunk, terurut dari yang paling relevan
            (distance terkecil) versi vector search.
        bm25_ranked_ids: List id chunk, terurut dari yang paling relevan
            (skor BM25 tertinggi) versi lexical search.
        k: Konstanta RRF, default 60.

    Returns:
        Dict {chunk_id: rrf_score}, belum diurutkan.
    """
    scores: dict[str, float] = {}

    for rank, chunk_id in enumerate(vector_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, chunk_id in enumerate(bm25_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    return scores


# Cache indeks BM25 di level modul (pola singleton, sama seperti _embedding_model
# dan _chroma_collection di embedding_service).
#
# Membangun BM25 berarti menarik SELURUH korpus dari ChromaDB lalu men-tokenisasi
# semuanya — biayanya sebanding dengan besar korpus. Sebelumnya itu dilakukan pada
# SETIAP pertanyaan, padahal isi korpus tidak berubah di antara dua pertanyaan;
# hanya berubah saat ada ingest/hapus dokumen. Pada korpus besar, beban itu
# tertambahkan ke tiap query dan terus tumbuh seiring dokumen bertambah.
_bm25_cache: dict | None = None


def invalidate_bm25_cache() -> None:
    """Buang cache indeks BM25. Dipanggil setelah dokumen di-ingest atau dihapus
    supaya query berikutnya membangun ulang indeks dari korpus terbaru."""
    global _bm25_cache
    if _bm25_cache is not None:
        logger.info("Cache BM25 di-invalidasi (korpus berubah)")
    _bm25_cache = None


def _get_bm25_index(collection) -> dict:
    """
    Mengembalikan indeks BM25 beserta korpusnya, dibangun sekali lalu dipakai ulang.

    Dua penanda dipakai untuk memutuskan apakah indeks lama masih sahih:

    1. `collection.count()` — menangkap penambahan atau penghapusan vektor.
    2. Penanda versi korpus di disk (`read_corpus_version`) — menangkap
       perubahan yang TIDAK mengubah jumlah vektor, misalnya menimpa dokumen
       dengan jumlah potongan yang kebetulan sama. Penanda ini juga satu-satunya
       jalan bagi proses ini untuk mengetahui ingest yang terjadi di proses
       pekerja Celery, karena cache di sini tidak terjangkau dari sana.

    Returns:
        Dict berisi bm25, docs, ids, metas, dan flag hierarchical.
    """
    global _bm25_cache

    try:
        current_count = collection.count()
    except Exception:
        current_count = -1

    current_version = read_corpus_version()

    if (
        _bm25_cache is not None
        and _bm25_cache["count"] == current_count
        and _bm25_cache["version"] == current_version
    ):
        return _bm25_cache

    with _bm25_lock:
        # Double check setelah memperoleh lock
        if (
            _bm25_cache is not None
            and _bm25_cache["count"] == current_count
            and _bm25_cache["version"] == current_version
        ):
            return _bm25_cache

        empty = {"bm25": None, "docs": [], "ids": [], "metas": [],
                 "hierarchical": True, "count": current_count,
                 "version": current_version}

        try:
            from rank_bm25 import BM25Okapi

            all_data = collection.get(where={"chunk_type": "child"})
            hierarchical = True
            if not all_data.get("documents"):
                # Data lama tanpa chunk_type — pakai seluruh koleksi (jalur flat)
                all_data = collection.get()
                hierarchical = False

            docs = all_data.get("documents", [])
            ids = all_data.get("ids", [])
            metas = all_data.get("metadatas", [])

            tokenized_corpus = [doc.lower().split() for doc in docs]
            _bm25_cache = {
                "bm25": BM25Okapi(tokenized_corpus) if tokenized_corpus else None,
                "docs": docs,
                "ids": ids,
                "metas": metas,
                "hierarchical": hierarchical,
                "count": current_count,
                "version": current_version,
            }
            logger.info(
                "Indeks BM25 dibangun: %d chunk (%s) — akan dipakai ulang sampai korpus berubah",
                len(docs), "hierarchical" if hierarchical else "flat",
            )
            return _bm25_cache
        except Exception as e:
            logger.warning(f"BM25 initialization failed: {e}")
            _bm25_cache = None  # jangan cache kegagalan
            return empty


def _build_where_filter(
    chunk_type: str | None,
    document_ids: list[int] | None,
) -> dict | None:
    """
    Menyusun filter `where` untuk ChromaDB dari dua kondisi opsional.

    ChromaDB butuh operator $and secara eksplisit bila ada lebih dari satu
    kondisi; satu kondisi harus dikirim polos tanpa $and.
    """
    conditions: list[dict] = []
    if chunk_type:
        conditions.append({"chunk_type": chunk_type})
    if document_ids:
        int_ids = [int(x) for x in document_ids if str(x).isdigit()]
        if int_ids:
            conditions.append(
                {"document_id": {"$in": int_ids}}
                if len(int_ids) > 1
                else {"document_id": int_ids[0]}
            )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _retrieve_context(
    query: str,
    original_query: str = "",
    document_ids: list[int] | None = None,
    top_k_override: int | None = None,
    return_chunks_info: bool = False,
) -> tuple[str, str] | tuple[str, str, list[dict]]:
    """
    Melakukan pencarian similarity di ChromaDB berdasarkan query pengguna.
    Menggunakan strategi Parent-Child Retrieval + Hybrid Search (Vector + BM25)
    yang digabungkan dengan Reciprocal Rank Fusion (RRF):
    1. Cari child chunks (kecil, presisi) yang paling relevan lewat vector search
       DAN BM25 secara terpisah.
    2. Gabungkan kedua peringkat hasil menggunakan RRF agar chunk yang match
       leksikal lemah tidak mengalahkan chunk yang secara makna benar-benar relevan.
    3. Ambil parent chunks (besar, lengkap) sebagai konteks ke LLM.

    Fallback ke flat retrieval jika data lama tanpa chunk_type ditemukan.

    Args:
        query: Pertanyaan dari pengguna (biasanya versi kata kunci).
        original_query: Pertanyaan asli pengguna tanpa filtering (untuk deteksi intent).
        document_ids: Daftar ID dokumen untuk membatasi pencarian.
        top_k_override: Override jumlah chunk yang diambil (untuk testing sandbox).
        return_chunks_info: Bila True, mengembalikan tuple (context, sources, debug_chunks).

    Returns:
        Tuple (context_text, sources_text) atau (context_text, sources_text, debug_chunks).
    """
    collection = get_chroma_collection()
    reranker = get_reranker_model()

    check_query = original_query if original_query else query
    is_list = _is_list_query(check_query)
    base_k = top_k_override if top_k_override is not None else _TOP_K
    max_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if is_list else max(base_k + 2, _MAX_CONTEXT_CHUNKS)

    # Bila reranker aktif, perluas pencarian awal (Stage 1 High Recall) agar kandidat lebih komprehensif
    if reranker is not None:
        stage1_k = max(base_k * 3, settings.RERANKER_TOP_CANDIDATES)
        top_k = base_k * 4 if is_list else stage1_k
    else:
        top_k = base_k * 4 if is_list else base_k

    if is_list:
        logger.info("Query terdeteksi sebagai list-query, max_chunks dinaikkan ke %d, top_k ke %d", max_chunks, top_k)

    try:
        # Pertanyaan asli ikut dicari, tidak digantikan.
        #
        # `query` di sini adalah versi kata kunci hasil ekstraksi LLM. Ekstraksi
        # itu memang membuang kalimat pengantar yang mengaburkan pencarian, tapi
        # kadang ikut membuang kata pembatas yang justru menentukan — misalnya
        # "tetap" pada "cuti pegawai tetap". Bila hanya kata kunci yang dicari,
        # pembatas itu hilang dan dua daftar berbeda dalam satu dokumen
        # tercampur. Dengan keduanya dicari, RRF yang memutuskan mana yang lebih
        # relevan, bukan hasil ekstraksi kata kunci.
        queries = [query]

        if original_query and original_query.strip() != query.strip():
            queries.append(original_query)

        # Normalisasi slang/typo untuk query pencarian
        norm_q = tool_router.normalize_query(query)
        norm_orig = tool_router.normalize_query(original_query) if original_query else ""
        if norm_q and norm_q != query.lower():
            queries.append(norm_q)
        if norm_orig and norm_orig != original_query.lower() and norm_orig != norm_q:
            queries.append(norm_orig)

        # Deteksi akronim domain & tambahkan query spesifik
        search_corpus_text = f"{query} {original_query} {norm_q} {norm_orig}".lower()
        acronym_anchors = []
        for acr_key, full_name in _ACRONYM_EXPANSIONS.items():
            if _re.search(rf"\b{acr_key}\b", search_corpus_text):
                acronym_anchors.append(f"SOP {full_name}")
                acronym_anchors.append(f"Prosedur {full_name}")
                acronym_anchors.append(full_name)

        if acronym_anchors:
            queries.extend(acronym_anchors)

        # Tambahkan anchor kata kunci inti untuk meningkatkan recall pada pertanyaan percakapan panjang
        clean_core = _re.sub(
            r"\b(jika|hari\s+ini|saya|mengajukan|pengajuan|untuk|kapan|siapnya|kapan\s+siapnya|estimasinya|estimasi|berapa|lama|proses|syarat|prosedur|tata\s+cara|langkah)\b",
            " ",
            query,
            flags=_re.IGNORECASE,
        ).strip()
        clean_core = " ".join(clean_core.split())
        if clean_core and len(clean_core) >= 4 and clean_core.lower() != query.lower():
            queries.append(f"SOP {clean_core}")
            queries.append(f"Pelaksanaan {clean_core}")
            queries.append(clean_core)

        if is_list:
            # Anchor query membantu menemukan halaman yang memuat daftar/enumerasi master SOP
            queries.extend([
                "Standar Operasional Prosedur sebagaimana dimaksud dalam Diktum Kesatu terdiri dari",
                "Diktum KEDUA Standar Operasional Prosedur",
                "MEMUTUSKAN Menetapkan KESATU KEDUA",
                "Penyusunan Rencana Strategis Renstra Penyusunan Rencana Kerja Renja",
                "daftar Standar Operasional Prosedur SOP",
                "Layanan Permintaan Data Sektoral",
            ])
            logger.info("List-query: menambahkan %d anchor query untuk retrieve halaman daftar", len(queries) - 1)

        # ── Tahap 1: Cari child chunks yang relevan (Hybrid BM25 + Vector, digabung via RRF) ──
        chunk_data: dict[str, tuple[str, dict]] = {}  # id -> (doc_text, metadata)

        bm25_index = _get_bm25_index(collection)
        bm25 = bm25_index["bm25"]
        all_docs = bm25_index["docs"]
        all_ids = bm25_index["ids"]
        all_metas = bm25_index["metas"]
        use_hierarchical = bm25_index["hierarchical"]

        aggregated_rrf: dict[str, float] = {}

        for q in queries:
            q_embedding = encode_query(q)

            # 1a. Vector Search (Semantic) — hasil SUDAH terurut dari yang paling relevan
            try:
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=top_k,
                    where=_build_where_filter(
                        "child" if use_hierarchical else None, document_ids
                    ),
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                use_hierarchical = False
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=top_k,
                    where=_build_where_filter(None, document_ids),
                    include=["documents", "metadatas", "distances"],
                )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            ids = results.get("ids", [[]])[0]

            vector_ranked_ids = list(ids)
            for chunk_id, doc_text, metadata in zip(ids, docs, metas):
                chunk_data[chunk_id] = (doc_text, metadata)

            # 1b. BM25 Search (Lexical / Kata Kunci)
            bm25_ranked_ids: list[str] = []
            if bm25 and all_docs:
                import numpy as np

                # Filter kata-kata generik domain kedinasan agar kata topik spesifik (mis: 'subdomain', 'cuti') tidak tenggelam
                domain_stopwords = {
                    "persyaratan", "syarat", "pengajuan", "layanan", "sop", "prosedur", "tata", "cara",
                    "bagaimana", "apa", "saja", "tentang", "pada", "dinas", "kota", "banda", "aceh",
                    "untuk", "dari", "dan", "yang", "di", "ke", "ini", "itu", "diskominfotik", "diskominfo"
                }
                raw_tokens = q.lower().split()
                meaningful_tokens = [w for w in raw_tokens if w not in domain_stopwords]
                tokenized_query = meaningful_tokens if meaningful_tokens else raw_tokens
                bm25_scores = bm25.get_scores(tokenized_query)
                if top_k > 0 and len(all_docs) > 0:
                    # Indeks BM25 dibangun atas SELURUH korpus (agar bisa di-cache),
                    # jadi pembatasan dokumen diterapkan di sini saat menyaring hasil.
                    # Urutan diambil penuh lalu dipotong setelah filter, supaya jatah
                    # top_k tidak habis terpakai oleh dokumen yang justru dikecualikan.
                    doc_filter = {int(x) for x in document_ids if str(x).isdigit()} if document_ids else None
                    for idx in np.argsort(bm25_scores)[::-1]:
                        if len(bm25_ranked_ids) >= top_k:
                            break
                        score = bm25_scores[idx]
                        if score <= _BM25_MIN_SCORE:
                            break  # sisanya pasti lebih kecil — hemat iterasi
                        meta_doc_id = all_metas[idx].get("document_id")
                        if doc_filter is not None and (meta_doc_id is None or int(meta_doc_id) not in doc_filter):
                            continue
                        b_id = all_ids[idx]
                        bm25_ranked_ids.append(b_id)
                        if b_id not in chunk_data:
                            chunk_data[b_id] = (all_docs[idx], all_metas[idx])

            # 1c. Gabungkan peringkat vector & BM25 via RRF
            rrf_scores = _reciprocal_rank_fusion(vector_ranked_ids, bm25_ranked_ids)
            for chunk_id, score in rrf_scores.items():
                aggregated_rrf[chunk_id] = aggregated_rrf.get(chunk_id, 0.0) + score

        if not aggregated_rrf:
            logger.info("Tidak ada dokumen relevan ditemukan untuk query: '%s'", query[:80])
            if return_chunks_info:
                return "", "", []
            return "", ""

        initial_ranked_ids = sorted(
            aggregated_rrf.keys(),
            key=lambda cid: aggregated_rrf[cid],
            reverse=True,
        )

        # ── Tahap 2: CrossEncoder Reranking (BGE-Reranker) ──
        # Menghitung relevansi mendalam pasangan (query, chunk) untuk menyaring false-positives
        # dan memprioritaskan potongan paling presisi.
        rerank_scores: dict[str, float] = {}

        if reranker is not None and initial_ranked_ids:
            scoring_query = original_query.strip() if original_query and original_query.strip() else query.strip()
            candidate_limit = max(settings.RERANKER_TOP_CANDIDATES, 40) if is_list else settings.RERANKER_TOP_CANDIDATES
            candidates_to_rerank = initial_ranked_ids[:candidate_limit]

            try:
                if is_list:
                    list_anchors = [
                        scoring_query,
                        "Standar Operasional Prosedur sebagaimana dimaksud dalam Diktum Kesatu terdiri dari",
                        "Diktum KEDUA Standar Operasional Prosedur",
                        "daftar Standar Operasional Prosedur SOP",
                    ]
                    all_pairs = [(sq, chunk_data[cid][0]) for cid in candidates_to_rerank for sq in list_anchors]
                    raw_scores = reranker.predict(all_pairs, batch_size=32)
                    n_anchors = len(list_anchors)
                    for i, cid in enumerate(candidates_to_rerank):
                        c_scores = raw_scores[i * n_anchors : (i + 1) * n_anchors]
                        rerank_scores[cid] = float(max(c_scores))
                else:
                    scoring_anchors = [query.strip()]
                    if original_query and original_query.strip() != query.strip():
                        scoring_anchors.append(original_query.strip())
                    if norm_q and norm_q not in scoring_anchors:
                        scoring_anchors.append(norm_q)
                    if norm_orig and norm_orig not in scoring_anchors:
                        scoring_anchors.append(norm_orig)
                    if acronym_anchors:
                        scoring_anchors.extend(acronym_anchors[:4])
                    if clean_core:
                        scoring_anchors.append(f"SOP {clean_core}")
                        scoring_anchors.append(f"Pelaksanaan {clean_core}")
                    elif not query.lower().startswith("sop "):
                        scoring_anchors.append(f"SOP {query.strip()}")

                    all_pairs = [(sq, chunk_data[cid][0]) for cid in candidates_to_rerank for sq in scoring_anchors]
                    raw_scores = reranker.predict(all_pairs, batch_size=32)
                    n_anchors = len(scoring_anchors)
                    for i, cid in enumerate(candidates_to_rerank):
                        c_scores = raw_scores[i * n_anchors : (i + 1) * n_anchors]
                        rerank_scores[cid] = float(max(c_scores))

                # Filter potongan yang berada di bawah ambang batas relevansi minimum
                surviving_ids = [
                    cid for cid in candidates_to_rerank
                    if rerank_scores[cid] >= settings.RERANKER_MIN_SCORE
                ]

                if surviving_ids:
                    ranked_chunk_ids = sorted(
                        surviving_ids,
                        key=lambda cid: rerank_scores[cid],
                        reverse=True,
                    )
                    top_score = rerank_scores[ranked_chunk_ids[0]]

                    # Dynamic Adaptive Pruning (Relative Gap & Score-Drop Cutoff)
                    # Pangkas potongan yang skornya anjlok jauh di bawah peringkat #1
                    if len(ranked_chunk_ids) > 1:
                        if is_list:
                            # Pada list query: jika terdapat chunk master daftar dengan keyakinan sangat tinggi (>= 0.90),
                            # perketat cutoff ke 0.90 agar potongan rincian SOP tunggal tidak ikut terseret.
                            if top_score >= 0.90:
                                relative_cutoff = 0.90
                            elif top_score >= 0.70:
                                relative_cutoff = max(0.50, top_score * 0.60)
                            else:
                                relative_cutoff = settings.RERANKER_MIN_SCORE
                        else:
                            # Rasio toleransi: pertahankan chunk yang skornya minimal 50% dari skor peringkat #1 bila positif
                            if top_score > 0:
                                relative_cutoff = max(settings.RERANKER_MIN_SCORE, top_score * 0.50)
                                if top_score >= 0.15:
                                    relative_cutoff = max(relative_cutoff, top_score * 0.60)
                            else:
                                relative_cutoff = settings.RERANKER_MIN_SCORE

                        pruned_ids = [
                            cid for cid in ranked_chunk_ids
                            if rerank_scores[cid] >= relative_cutoff
                        ]
                        if pruned_ids:
                            ranked_chunk_ids = pruned_ids

                    logger.info(
                        "BGE-Reranker: %d kandidat dinilai -> %d chunk lolos cutoff dinamis (skor terbaik: %.4f, terendah: %.4f)",
                        len(candidates_to_rerank),
                        len(ranked_chunk_ids),
                        rerank_scores[ranked_chunk_ids[0]],
                        rerank_scores[ranked_chunk_ids[-1]],
                    )
                else:
                    logger.info(
                        "BGE-Reranker: seluruh %d kandidat di bawah threshold %.4f (pertanyaan di luar domain)",
                        len(candidates_to_rerank),
                        settings.RERANKER_MIN_SCORE,
                    )
                    ranked_chunk_ids = []
            except Exception as e:
                logger.warning("BGE-Reranker gagal inferensi, fallback ke urutan RRF: %s", e)
                ranked_chunk_ids = initial_ranked_ids
        else:
            ranked_chunk_ids = initial_ranked_ids

        if not ranked_chunk_ids:
            logger.info("Tidak ada dokumen yang lolos ambang batas reranker untuk query: '%s'", query[:80])
            if return_chunks_info:
                return "", "", []
            return "", ""

        # ── Tahap 3: Ambil parent chunks dari child yang cocok ──
        if use_hierarchical:
            child_limit = len(ranked_chunk_ids) if is_list else base_k
            top_children_ids = ranked_chunk_ids[:child_limit]

            parent_ids_ordered: list[str] = []
            parent_best_score: dict[str, float] = {}
            parent_best_rerank: dict[str, float | None] = {}
            for chunk_id in top_children_ids:
                _, metadata = chunk_data[chunk_id]
                pid = metadata.get("parent_id")
                score = aggregated_rrf.get(chunk_id, 0.0)
                r_score = rerank_scores.get(chunk_id)
                if pid and pid not in parent_best_score:
                    parent_ids_ordered.append(pid)
                    parent_best_score[pid] = score
                    parent_best_rerank[pid] = r_score
                elif pid:
                    if score > parent_best_score.get(pid, float("-inf")):
                        parent_best_score[pid] = score
                    if r_score is not None:
                        curr_r = parent_best_rerank.get(pid)
                        if curr_r is None or r_score > curr_r:
                            parent_best_rerank[pid] = r_score

            if parent_ids_ordered:
                parent_results = collection.get(
                    ids=parent_ids_ordered,
                    include=["documents", "metadatas"],
                )

                parent_docs = parent_results.get("documents", [])
                parent_metas = parent_results.get("metadatas", [])
                parent_ret_ids = parent_results.get("ids", [])

                combined = []
                for pid, doc, meta in zip(parent_ret_ids, parent_docs, parent_metas):
                    score = parent_best_score.get(pid, 0.0)
                    r_score = parent_best_rerank.get(pid)
                    combined.append((doc, meta, score, r_score))

                # Jika reranker aktif, utamakan pengurutan parent berdasarkan skor rerank tertinggi
                if reranker is not None and any(x[3] is not None for x in combined):
                    combined.sort(key=lambda x: (x[3] if x[3] is not None else -1.0), reverse=True)
                    top_parent_score = combined[0][3] if combined[0][3] is not None else 0.0
                    if top_parent_score > 0 and len(combined) > 1:
                        if is_list:
                            if top_parent_score >= 0.90:
                                parent_cutoff = 0.90
                            elif top_parent_score >= 0.70:
                                parent_cutoff = max(0.50, top_parent_score * 0.60)
                            else:
                                parent_cutoff = settings.RERANKER_MIN_SCORE
                        else:
                            parent_cutoff = max(settings.RERANKER_MIN_SCORE, top_parent_score * 0.50)
                            if top_parent_score >= 0.15:
                                parent_cutoff = max(parent_cutoff, top_parent_score * 0.60)
                        pruned_combined = [x for x in combined if (x[3] is not None and x[3] >= parent_cutoff)]
                        if pruned_combined:
                            combined = pruned_combined
                else:
                    combined.sort(key=lambda x: x[2], reverse=True)

                combined = combined[:max_chunks]

                # SOP Sibling Pairing:
                # Bila bukan list query, setiap chunk SOP (Identitas atau Prosedur) harus dilengkapi dengan
                # seluruh halaman pasangannya dari SOP yang sama agar LLM mendapatkan konteks prosedur & identitas yang utuh.
                if not is_list and combined:
                    paired_combined = list(combined)
                    existing_p_keys = {
                        (int(m.get("document_id", 0)), int(m.get("page_number", 0)))
                        for _, m, _, _ in combined
                    }
                    sop_contexts_to_fetch = set()
                    for d_text, m, _, _ in combined:
                        d_id = m.get("document_id")
                        if not d_id or not str(d_id).isdigit():
                            continue
                        ctx_match = _re.search(r'\[Konteks:\s*(.*?)\]', d_text, _re.IGNORECASE)
                        if ctx_match:
                            c_tag = ctx_match.group(1).strip()
                            if "sop" in c_tag.lower():
                                sop_contexts_to_fetch.add((int(d_id), c_tag.lower()))

                    if sop_contexts_to_fetch:
                        for d_id, c_tag_lower in sop_contexts_to_fetch:
                            try:
                                all_doc_parents = collection.get(
                                    where={"$and": [{"document_id": d_id}, {"chunk_type": "parent"}]},
                                    include=["documents", "metadatas"],
                                )
                                sib_docs = all_doc_parents.get("documents", [])
                                sib_metas = all_doc_parents.get("metadatas", [])
                                for s_doc, s_meta in zip(sib_docs, sib_metas):
                                    s_page = int(s_meta.get("page_number", 0))
                                    if (d_id, s_page) in existing_p_keys:
                                        continue
                                    s_ctx_match = _re.search(r'\[Konteks:\s*(.*?)\]', s_doc, _re.IGNORECASE)
                                    if s_ctx_match and s_ctx_match.group(1).strip().lower() == c_tag_lower:
                                        paired_combined.append((s_doc, s_meta, 0.0, 1.0))
                                        existing_p_keys.add((d_id, s_page))
                            except Exception as e:
                                logger.warning("Gagal fetch sibling SOP parent chunks: %s", e)

                    combined = paired_combined

                # Jika list query dan memuat potongan Diktum KEDUA / MEMUTUSKAN,
                # pastikan seluruh halaman lanjutan diktum tersebut tersambung utuh.
                if is_list:
                    expanded_combined = list(combined)
                    for doc_text, meta, score, r_score in combined:
                        doc_lower = doc_text.lower()
                        if "diktum kesatu terdiri dari" in doc_lower or "kedua :" in doc_lower or "memutuskan :" in doc_lower:
                            doc_id = meta.get("document_id")
                            page_num = meta.get("page_number", 1)
                            if doc_id:
                                next_results = collection.get(
                                    where={"$and": [{"document_id": doc_id}, {"chunk_type": "parent"}]},
                                    include=["documents", "metadatas"],
                                )
                                all_p_docs = next_results.get("documents", [])
                                all_p_metas = next_results.get("metadatas", [])
                                p_by_page = {pm.get("page_number"): (pd, pm) for pd, pm in zip(all_p_docs, all_p_metas)}

                                curr_page = page_num + 1
                                while curr_page in p_by_page:
                                    pdoc, pmeta = p_by_page[curr_page]
                                    if not any(pm.get("page_number") == curr_page and pm.get("document_id") == doc_id for _, pm, _, _ in expanded_combined):
                                        expanded_combined.append((pdoc, pmeta, score, 1.0))
                                    pdoc_lower = pdoc.lower()
                                    if "ketiga :" in pdoc_lower or "diktum ketiga" in pdoc_lower or "ditetapkan di banda aceh" in pdoc_lower:
                                        break
                                    curr_page += 1
                    combined = expanded_combined

                # Batasi maksimum chunk terakumulasi agar tidak meluap melampaui context window LLM
                max_allowed_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if is_list else (_MAX_CONTEXT_CHUNKS + 6)
                if len(combined) > max_allowed_chunks:
                    combined = combined[:max_allowed_chunks]

                # Sort ulang untuk presentasi ke LLM berdasarkan urutan dokumen (page + chunk_index)
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))

                logger.info(
                    "Two-Stage RAG: %d child cocok -> %d parent unik -> %d dikirim ke LLM",
                    len(ranked_chunk_ids), len(parent_ids_ordered), len(combined),
                )
            else:
                combined = [
                    (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf.get(cid, 0.0), rerank_scores.get(cid))
                    for cid in ranked_chunk_ids[:max_chunks]
                ]
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))
        else:
            combined = [
                (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf.get(cid, 0.0), rerank_scores.get(cid))
                for cid in ranked_chunk_ids[:max_chunks]
            ]
            combined.sort(key=lambda x: (
                int(x[1].get("page_number", 0)),
                int(x[1].get("chunk_index", 0)),
            ))
            logger.info(
                "Flat retrieval (fallback): %d chunk dipilih dari %d total",
                len(combined), len(ranked_chunk_ids),
            )

        # ── Tahap 4: Bangun teks konteks dan sumber ──
        context_parts: list[str] = []
        doc_pages_for_sources: dict[str, set[int]] = {}
        non_page_sources: set[str] = set()

        # Ambil nama asli dokumen dari database untuk sitasi yang informatif
        doc_ids_set = {
            int(meta.get("document_id"))
            for _, meta, _, _ in combined
            if meta.get("document_id") is not None and str(meta.get("document_id")).isdigit()
        }
        doc_names_map: dict[int, str] = {}
        if doc_ids_set:
            try:
                doc_names_map = get_document_names_by_ids(doc_ids_set)
            except Exception as e:
                logger.warning("Gagal mengambil nama dokumen untuk sitasi: %s", str(e))

        debug_chunks: list[dict] = []
        for doc_text, metadata, rrf_score, r_score in combined:
            doc_id = metadata.get("document_id", "?")
            page_num = metadata.get("page_number", "?")
            chunk_idx = metadata.get("chunk_index", "?")
            chunk_type = metadata.get("chunk_type", "flat")

            doc_name = doc_names_map.get(int(doc_id)) if str(doc_id).isdigit() else None
            display_title = doc_name or f"Dokumen #{doc_id}"

            score_labels = [f"skor RRF: {rrf_score:.4f}"]
            if r_score is not None:
                score_labels.append(f"Rerank: {r_score:.4f}")
            score_str = ", ".join(score_labels)

            context_parts.append(
                f"[Sumber: {display_title}, Halaman {page_num}, "
                f"Chunk #{chunk_idx} ({chunk_type}) "
                f"({score_str})]\n{doc_text}"
            )

            # Agregasikan nomor halaman per dokumen
            if str(page_num).isdigit():
                doc_pages_for_sources.setdefault(display_title, set()).add(int(page_num))
            else:
                non_page_sources.add(f"{display_title} — Halaman {page_num}")

            if return_chunks_info:
                chunk_item = {
                    "id": metadata.get("chunk_id", f"{doc_id}-{page_num}-{chunk_idx}"),
                    "document_id": doc_id,
                    "document_name": display_title,
                    "page_number": page_num,
                    "chunk_index": chunk_idx,
                    "chunk_type": chunk_type,
                    "rrf_score": round(float(rrf_score), 4),
                    "content": doc_text,
                }
                if r_score is not None:
                    chunk_item["rerank_score"] = round(float(r_score), 4)
                debug_chunks.append(chunk_item)

        context_text = "\n\n---\n\n".join(context_parts)

        # Susun daftar sumber yang ringkas, bersih, dan teragregasi
        sources_lines: list[str] = []
        for d_title in sorted(doc_pages_for_sources.keys()):
            pages_list = sorted(doc_pages_for_sources[d_title])
            sources_lines.append(f"- {d_title} - {_format_pages_list(pages_list)}")
        for np in sorted(non_page_sources):
            sources_lines.append(f"- {np}")

        sources_text = "\n".join(sources_lines)

        best_score = max(aggregated_rrf.values()) if aggregated_rrf else 0.0
        logger.info(
            "Ditemukan %d konteks unik dari %d query (skor RRF terbaik: %.4f), "
            "dikirim %d chunk ke LLM",
            len(ranked_chunk_ids),
            len(queries),
            best_score,
            len(combined),
        )

        if settings.DEBUG_DUMP_CONTEXT:
            try:
                with open("debug_context.txt", "w", encoding="utf-8") as f:
                    f.write(context_text)
            except OSError as e:
                logger.warning("Gagal menulis debug_context.txt: %s", e)

        if return_chunks_info:
            return context_text, sources_text, debug_chunks
        return context_text, sources_text

    except Exception:
        # exc_info=True: tanpa jejak lengkapnya, kegagalan retrieval tidak bisa
        # dibedakan dari "memang tidak ada dokumen yang relevan".
        logger.error("Gagal melakukan pencarian konteks", exc_info=True)
        if return_chunks_info:
            return "", "", []
        return "", ""




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


# ─────────────────────────────────────────────────────────────
# JENDELA KONTEKS & KETAHANAN TERHADAP KEGAGALAN ALOKASI
# ─────────────────────────────────────────────────────────────

def _estimasi_token_konteks(context_text: str) -> int:
    """
    Menaksir jumlah token pada konteks + jawaban, HANYA untuk ditampilkan di
    telemetri. Tidak lagi menentukan jendela — num_ctx dipatok ke
    settings.LLM_NUM_CTX atau setelan database (lihat catatan konstanta di atas).

    Pembaginya sengaja kecil supaya taksirannya melebihkan.
    """
    perlu = int(len(context_text) / _CHARS_PER_TOKEN) + _NUM_CTX_RESPONSE_HEADROOM
    return math.ceil(perlu / 1024) * 1024


# Penanda bahwa kegagalan berasal dari memori, bukan sebab lain. Dicocokkan
# pada teks pesan karena Ollama meneruskannya sebagai ResponseError biasa —
# tidak ada tipe exception khusus yang bisa dibedakan.
_PENANDA_GAGAL_ALOKASI = (
    "failed to allocate",
    "out-of-memory",
    "out of memory",
    "cannot allocate",
    "llama-server process has terminated",
)


def _gagal_alokasi(e: Exception) -> bool:
    """Apakah kegagalan ini soal memori."""
    pesan = str(e).lower()
    return any(p in pesan for p in _PENANDA_GAGAL_ALOKASI)


def _stream_jawaban(
    system_prompt: str,
    query: str,
    temperature: float = 0.0,
    num_ctx: int = settings.LLM_NUM_CTX,
    chat_history: list[dict[str, str]] | None = None,
    model_name: str | None = None,
) -> Generator[str, None, None]:
    """
    Alirkan jawaban LLM pada jendela konteks aktif dengan dukungan riwayat multi-turn.
    """
    messages = [SystemMessage(content=system_prompt)]
    if chat_history:
        import re
        for msg in chat_history[-4:]:
            role = msg.get("role")
            cnt = msg.get("content", "")
            if cnt:
                if role == "user":
                    messages.append(HumanMessage(content=cnt))
                elif role == "assistant":
                    # Sanitize: Remove previous system-appended citations to break the LLM's pattern recognition
                    cnt_bersih = re.sub(r"(?i)\n*?\**Sumber Referensi:\**.*", "", cnt, flags=re.DOTALL)
                    messages.append(AIMessage(content=cnt_bersih))
    messages.append(HumanMessage(content=query))

    jendela_dicoba = [num_ctx]
    if _NUM_CTX_FALLBACK < num_ctx:
        jendela_dicoba.append(_NUM_CTX_FALLBACK)

    for i, jendela in enumerate(jendela_dicoba):
        sudah_terkirim = False
        try:
            llm = ChatOllama(
                model=model_name or settings.LLM_MODEL_NAME,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature,
                num_ctx=jendela,
                num_gpu=_NUM_GPU,
                # Matikan mode thinking — lihat catatan di _correct_query_typos().
                # Tanpa ini, model thinking (qwen3.5) mengembalikan konten kosong.
                reasoning=False,
                keep_alive=_OLLAMA_KEEP_ALIVE,
                client_kwargs={"timeout": _OLLAMA_TIMEOUT},
                stop=["**Sumber Referensi:**", "Sumber Referensi:"]
            )
            for chunk in llm.stream(messages):
                if chunk.content:
                    sudah_terkirim = True
                    yield chunk.content
            return

        except Exception as e:
            if sudah_terkirim or i == len(jendela_dicoba) - 1 or not _gagal_alokasi(e):
                raise
            logger.warning(
                "Ollama gagal mengalokasikan memori pada num_ctx=%d — dicoba ulang sekali dengan %d",
                jendela, jendela_dicoba[i + 1],
            )


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def generate_response(
    query: str,
    session_id: str,
    document_ids: list[int] | None = None,
    system_prompt_override: str | None = None,
    temperature_override: float | None = None,
    top_k_override: int | None = None,
    include_debug: bool = False,
) -> Generator[str | dict, None, None]:
    """
    Menghasilkan respons RAG secara streaming.

    Langkah-langkah:
    1. Ambil konfigurasi prompt & chatbot aktif dari database (atau override sandbox).
    2. Cari konteks relevan di ChromaDB.
    3. Jika include_debug aktif, kirim event metadata chunk terlebih dahulu.
    4. Jika pertanyaan minta prosedur tapi konteks cuma daftar nama SOP,
       jawab langsung tanpa perlu panggil LLM.
    5. Bangun prompt dengan konteks (+ tabel perbandingan jika relevan).
    6. Panggil LLM Ollama dan stream hasilnya.
    7. Sertakan referensi sumber di akhir bila diaktifkan.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat (untuk logging dan tracking).
        document_ids: Bila diisi, pencarian dibatasi hanya pada dokumen tersebut.
        system_prompt_override: Override system prompt (opsional, untuk playground sandbox).
        temperature_override: Override temperature (opsional, untuk playground sandbox).
        top_k_override: Override top-k retrieval (opsional, untuk playground sandbox).
        include_debug: Bila True, yield dict berisi chunks metadata sebelum teks jawaban.

    Yields:
        String atau Dict berisi chunk respons dan metadata debug.
    """
    logger.info(
        "Memulai generate response — session=%s, query='%s'",
        session_id,
        query[:80],
    )

    try:
        # 1. Ambil konfigurasi chatbot & RAG aktif
        rag_cfg = get_chatbot_rag_config()
        active_llm_model = rag_cfg.get("llm_model_name") or settings.LLM_MODEL_NAME
        chatbot_name = rag_cfg.get("chatbot_name", "Asisten Virtual Diskominfotik")
        chatbot_persona = rag_cfg.get("chatbot_persona", "Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh")

        raw_template = (
            system_prompt_override
            if system_prompt_override is not None and system_prompt_override.strip()
            else (rag_cfg.get("rag_system_prompt") or _SYSTEM_PROMPT)
        )

        active_prompt_template = raw_template.replace("{chatbot_name}", chatbot_name).replace("{chatbot_persona}", chatbot_persona)
        if chatbot_name and chatbot_name not in active_prompt_template:
            active_prompt_template = f"Identitas: {chatbot_name}\nPersona: {chatbot_persona}\n\n" + active_prompt_template

        temperature = (
            temperature_override
            if temperature_override is not None
            else rag_cfg.get("rag_temperature", 0.0)
        )
        active_top_k = (
            top_k_override
            if top_k_override is not None
            else rag_cfg.get("rag_top_k", _TOP_K)
        )
        active_num_ctx = int(rag_cfg.get("rag_num_ctx", settings.LLM_NUM_CTX))
        fallback_msg = rag_cfg.get("chatbot_fallback_message") or "Mohon maaf, informasi terkait hal tersebut belum tersedia di dalam dokumen SOP kami. Jika Anda ingin dibantu langsung oleh tim Diskominfotik, silakan beri tahu saya ya."
        citation_enabled = rag_cfg.get("rag_citation_enabled", True)

        # 2. Fast-Path Intent Routing & Agentic Tools dengan Context Memory
        chat_history = session_memory.get_session_history(session_id, max_turns=4)
        route_result = tool_router.route_intent(query, session_id=session_id)
        intent = route_result["intent"]
        route_label = route_result.get("label", "Fast-Path Routing")
        route_params = route_result.get("params", {})

        if intent == "human_escalation":
            handoff_msg = (
                "Baik, pesan Anda sudah saya teruskan ke tim kami untuk dibantu lebih lanjut. "
                "Agar tim kami dapat membantu lebih cepat, silakan tinggalkan **Nama/Instansi** dan **detail kendala** Anda di sini ya. "
                "Selain itu, Anda juga dapat menghubungi Call Center 112 atau berkonsultasi langsung di kantor Diskominfotik "
                "(Balai Kota Banda Aceh, Gedung C Lantai 3). Terima kasih!"
            )
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": "Bantuan Tim Diskominfotik (Handover)",
                    "detail": "Pengguna meminta bantuan langsung dari tim manusia. Meneruskan ke antrean tindak lanjut...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": True,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, handoff_msg, topic="Permintaan Bantuan Petugas")
            yield handoff_msg
            return

        if intent == "human_escalation_followup":
            followup_ack = (
                "Terima kasih atas informasinya. Catatan tambahan Anda sudah saya simpan dan diteruskan ke tim Diskominfotik "
                "untuk ditindaklanjuti. Mohon ditunggu respon dari tim kami ya!"
            )
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": "Catatan Tambahan untuk Petugas",
                    "detail": "Menyimpan data identitas/kendala pengguna ke antrean tindak lanjut...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": True,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, followup_ack, topic="Permintaan Bantuan Petugas")
            yield followup_ack
            return

        if intent == "session_recap":
            is_empty_history = not chat_history or len(chat_history) == 0
            if is_empty_history:
                recap_msg = (
                    "Kita baru saja memulai sesi percakapan ini dan belum membahas topik tertentu. "
                    "Ada informasi seputar layanan atau dokumen SOP di Diskominfotik Kota Banda Aceh yang dapat saya bantu?"
                )
                if include_debug:
                    yield {
                        "type": "trace",
                        "stage": "intent_routing",
                        "step": 1,
                        "total_steps": 1,
                        "label": "Rangkuman Memori Sesi",
                        "detail": "Sesi belum memiliki riwayat obrolan terdahulu.",
                    }
                    yield {
                        "type": "debug",
                        "chunks": [],
                        "total_chunks": 0,
                    }
                    yield {
                        "type": "telemetry",
                        "model_name": active_llm_model,
                        "context_tokens": 0,
                        "num_ctx": active_num_ctx,
                        "chunks_count": 0,
                        "is_fallback": False,
                    }
                session_memory.add_user_message(session_id, query)
                session_memory.add_assistant_message(session_id, recap_msg, topic="Rangkuman Sesi")
                yield recap_msg
                return

            history_lines = []
            for m in chat_history:
                role_label = "Pengguna" if m.get("role") == "user" else "Asisten"
                content_text = m.get("content", "").strip()
                if content_text:
                    history_lines.append(f"{role_label}: {content_text}")

            history_formatted = "\n".join(history_lines)

            recap_prompt = f"""Anda adalah Asisten Virtual resmi Diskominfotik Kota Banda Aceh.
Pengguna menanyakan apa yang telah dibahas sebelumnya dalam percakapan ini.

Riwayat Percakapan yang Telah Berlangsung:
{history_formatted}

Instruksi:
1. Rangkum secara singkat, jelas, santun, dan bersahabat topik atau pertanyaan yang baru saja dibahas oleh pengguna di atas dalam 1-2 kalimat ringkas.
2. Akhiri dengan menawarkan bantuan lebih lanjut seputar layanan atau SOP Diskominfotik Kota Banda Aceh.
3. JANGAN mengarang informasi di luar riwayat percakapan di atas.
4. JANGAN menggunakan emoji."""

            estimasi_recap = _estimasi_token_konteks(recap_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": "Rangkuman Memori Sesi",
                    "detail": f"Membaca {len(chat_history)} pesan terdahulu dan merangkum obrolan...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                recap_prompt,
                query,
                temperature=0.2,
                num_ctx=active_num_ctx,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_recap = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_recap, topic="Rangkuman Sesi")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": estimasi_recap,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "chitchat":
            is_simple_hi = bool(re.match(r"^(?:halo|hai|hay|hei|hi|hello|assalamu['\s]?alaikum|ass|askum|saleuem|saleum|kru\s+seumangat|p|ping|tes|test)[\s,.-]*$", query.strip().lower()))
            is_followup = bool(chat_history and len(chat_history) > 0)

            if is_simple_hi and not is_followup:
                greeting_msg = rag_cfg.get("chatbot_greeting") or (
                    f"Halo! Saya adalah {chatbot_persona}. "
                    "Ada yang bisa saya bantu mengenai informasi SOP atau layanan Diskominfotik Kota Banda Aceh?"
                )
                if include_debug:
                    yield {
                        "type": "trace",
                        "stage": "intent_routing",
                        "step": 1,
                        "total_steps": 1,
                        "label": route_label,
                        "detail": "Input terdeteksi sebagai sapaan awal. Menjawab langsung...",
                    }
                    yield {
                        "type": "debug",
                        "chunks": [],
                        "total_chunks": 0,
                    }
                    yield {
                        "type": "telemetry",
                        "model_name": active_llm_model,
                        "context_tokens": 0,
                        "num_ctx": active_num_ctx,
                        "chunks_count": 0,
                        "is_fallback": False,
                    }
                session_memory.add_user_message(session_id, query)
                session_memory.add_assistant_message(session_id, greeting_msg, topic="Sapaan")
                yield greeting_msg
                return

            now_str = _get_current_date_info()
            inst_info_str = _get_institution_info()

            chitchat_prompt = f"""Anda adalah Asisten Virtual resmi Layanan Informasi Diskominfotik Kota Banda Aceh ({chatbot_name}) yang ramah, hangat, manusiawi, santun, dan profesional.

Waktu Acuan: {now_str}
Profil Singkat Instansi:
{inst_info_str}

Instruksi Komunikasi:
1. Respon percakapan santai pengguna (sapaan, tanya kabar/kondisi, apresiasi, atau pertanyaan identitas diri) secara ramah, natural, dan menyenangkan layaknya petugas Front Office yang melayani masyarakat.
2. Bila pengguna menanyakan kabar (misal: 'kamu gimana sehat?', 'apa kabar?'), jawab dengan ramah bahwa Anda dalam kondisi sangat baik dan siap membantu.
3. Bila pengguna menanyakan identitas/kemampuan (misal: 'kamu siapa?', 'bisa apa aja?'), jelaskan secara ringkas peran Anda sebagai asisten resmi yang membantu masyarakat dan ASN dalam mencari informasi SOP kedinasan dan layanan Diskominfotik Kota Banda Aceh.
4. Bila pengguna mengucapkan terima kasih/apresiasi, balas dengan ramah dan tulus.
5. Akhiri dengan menawarkan bantuan seputar layanan atau dokumen SOP Diskominfotik Kota Banda Aceh.
6. JANGAN memunculkan pesan 'tidak ditemukan di dokumen SOP' untuk obrolan santai ini.
7. JANGAN menggunakan emoji."""

            estimasi_chitchat = _estimasi_token_konteks(chitchat_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": "Obrolan Santai & Persona",
                    "detail": "Menjawab percakapan santai secara natural berbasis persona helpdesk...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                chitchat_prompt,
                query,
                temperature=0.3,
                num_ctx=active_num_ctx,
                chat_history=chat_history,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_resp = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_resp, topic="Percakapan Santai")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": estimasi_chitchat,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "augmented_knowledge":
            facts = route_params.get("facts_context", "")
            source_title = route_params.get("source_title", "Informasi Resmi")
            category = route_params.get("category", "instansi")
            now_str = _get_current_date_info()
            is_followup = bool(chat_history and len(chat_history) > 0)

            salam_guide = (
                "1. Percakapan Lanjutan (Multi-Turn): Karena ini adalah pertanyaan lanjutan dalam sesi percakapan yang sedang berjalan, JANGAN mengulang salam pembuka formal atau kalimat 'selamat datang' yang sama. Jawab langsung ke inti pertanyaan secara santun dan jelas."
                if is_followup
                else "1. Awali dengan salam pembuka yang ramah dan sopan (misal: 'Assalamu\\'alaikum / Halo, selamat datang di Layanan Informasi Diskominfotik Kota Banda Aceh')."
            )

            is_correction = _is_doubt_or_correction_query(query)
            if is_correction:
                apology_guide = (
                    "3. Penanganan Koreksi & Keraguan Pengguna: Karena pengguna meragukan atau mengoreksi jawaban sebelumnya:\n"
                    "   - Bersikaplah rendah hati, santun, dan profesional.\n"
                    "   - Awali dengan permohonan maaf atas kekeliruan sebelumnya secara santun (misal: 'Mohon maaf atas kekeliruan sebelumnya...').\n"
                    "   - Jelaskan perbaikan atau data yang benar dan akurat.\n"
                    "   - JANGAN menggunakan kata 'Tentu' saat meralat kesalahan sendiri.\n"
                    "   - JANGAN mengucapkan salam balasan jika pengguna tidak mengucapkan salam."
                )
            else:
                apology_guide = (
                    "3. Penjelasan Lugas & To-the-point: Jawab langsung pertanyaan pengguna secara lugas, santun, dan akurat berdasarkan Fakta Resmi di atas.\n"
                    "   - JANGAN meminta maaf dan JANGAN mengucapkan 'Mohon maaf atas kekeliruan' karena pengguna hanya mengajukan pertanyaan normal / pertanyaan lanjutan baru."
                )

            system_prompt = f"""Anda adalah Asisten Helpdesk dan Layanan Informasi Publik resmi Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh.
Tugas Anda adalah melayani masyarakat dan ASN dengan ramah, komunikatif, solutif, dan profesional layaknya petugas helpdesk / front office resmi.

WAKTU & TANGGAL ACUAN SAAT INI:
- Hari & Tanggal Hari Ini: {now_str}

FAKTA RESMI INSTANSI TERVERIFIKASI:
{facts}

PANDUAN KOMUNIKASI HELPDESK:
{salam_guide}
2. Sampaikan informasi inti secara jelas, lugas, dan akurat berdasarkan Fakta Resmi di atas.
{apology_guide}
4. Perhitungan Durasi Waktu: Bila pengguna menanyakan durasi/lama waktu sampai hari ini (misal 'sudah berapa hari/bulan/tahun menjabat'), hitung selisih waktu secara akurat dari tanggal peristiwa ke Hari & Tanggal Hari Ini ({now_str}).
5. Akhiri dengan kalimat penutup khas helpdesk yang ramah dan menawarkan bantuan lanjutan jika diperlukan (misal: 'Ada yang dapat kami bantu lagi terkait layanan Diskominfotik?').
6. Bila pertanyaan menggunakan Bahasa Aceh (misal: 'Saleuem', 'soe nan...', 'pat kanto...'), pahami maksudnya dan respon secara santun dalam Bahasa Indonesia dengan salam santun khas Aceh.
7. JANGAN menggunakan emoji atau karakter grafis.
8. ATURAN WAJIB (ANTI-HALUSINASI): Jawab HANYA menggunakan informasi yang tertulis secara eksplisit pada blok FAKTA RESMI INSTANSI TERVERIFIKASI di atas.
9. JIKA fakta di atas TIDAK memuat jawaban atau angka yang ditanyakan pengguna, ANDA WAJIB menjawab: "Maaf, informasi spesifik mengenai hal tersebut tidak tercantum dalam wawasan saya." DILARANG KERAS menggunakan wawasan umum Anda untuk menebak atau mengarang prosedur/angka/jadwal."""

            estimasi_token = _estimasi_token_konteks(system_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": route_label,
                    "detail": f"Menginjeksi fakta resmi [{source_title}] ke model {active_llm_model}...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "trace",
                    "stage": "generation",
                    "step": 2,
                    "total_steps": 2,
                    "label": "Sintesis Pengetahuan AI",
                    "detail": f"Menghasilkan respons natural berbasis fakta terverifikasi (~{estimasi_token} token)...",
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                system_prompt,
                query,
                temperature=temperature,
                num_ctx=active_num_ctx,
                chat_history=chat_history,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_resp = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(
                session_id,
                full_resp,
                topic=source_title,
                entity=route_params.get("search_query") or source_title,
            )

            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": f"{active_llm_model} (Fakta Instansi: {source_title})",
                    "context_tokens": estimasi_token,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "tool_calculator":
            calc_result = tool_router.hitung_estimasi_selesai(**route_params)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": route_label,
                    "detail": f"Mengeksekusi kalkulator hari kerja ({calc_result['lama_hari_kerja']} hari kerja)...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": f"{active_llm_model} (Tool: Kalkulator)",
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, calc_result["formatted_text"], topic="Kalkulator Hari Kerja")
            yield calc_result["formatted_text"]
            return

        resolved_query = route_params.get("query", query)
        corrected_query = tool_router.normalize_query(resolved_query) or resolved_query

        if include_debug:
            yield {
                "type": "trace",
                "stage": "retrieval",
                "step": 1,
                "total_steps": 3,
                "label": "Pencarian Vektor & BM25",
                "detail": "Mencari kandidat konteks di ChromaDB dan indeks leksikal...",
            }
            context_text, sources_text, debug_chunks = _retrieve_context(
                corrected_query,
                original_query=resolved_query,
                document_ids=document_ids,
                top_k_override=active_top_k,
                return_chunks_info=True,
            )
            yield {
                "type": "debug",
                "chunks": debug_chunks,
                "total_chunks": len(debug_chunks),
            }
            yield {
                "type": "trace",
                "stage": "ranking",
                "step": 2,
                "total_steps": 3,
                "label": "BGE-Reranker & RRF Ranking",
                "detail": f"Menghitung skor relevansi CrossEncoder dan merangking {len(debug_chunks)} potongan konteks...",
            }
        else:
            context_text, sources_text = _retrieve_context(
                corrected_query,
                original_query=resolved_query,
                document_ids=document_ids,
                top_k_override=active_top_k,
                return_chunks_info=False,
            )

        if not context_text:
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, fallback_msg, topic="Fallback")
            yield fallback_msg
            return

        # Guard: pertanyaan menyebut entitas bernomor yang tidak ada di dokumen
        # (Diktum KEEMPAT, langkah ke-11). Dipasang PALING AWAL karena jalur
        # daftar terprogram di bawah menjawab tanpa melibatkan LLM sama sekali,
        # sehingga tidak ada tahap lain yang berkesempatan menyadari premisnya
        # palsu — ditanya Diktum KEEMPAT, ia pernah memuntahkan 74 SOP milik
        # Diktum KEDUA dengan penuh percaya diri.
        entitas = _entitas_tak_ada_di_konteks(resolved_query, context_text)
        if entitas is not None:
            logger.info("Premis palsu: %s tidak ada di konteks", entitas)
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            msg = (
                f"Maaf, {entitas} tidak ditemukan di dalam dokumen. "
                "Pastikan penomorannya sesuai dengan isi dokumen."
            )
            if sources_text and citation_enabled:
                msg += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, msg, topic="Entitas Tidak Ditemukan")
            yield msg
            return

        # Guard: pertanyaan minta prosedur, tapi konteks yang ditemukan cuma
        # daftar nama SOP (tanpa rincian) → jangan biarkan LLM mengarang.
        if (
            _is_procedure_question(resolved_query)
            and _context_is_sop_document(context_text)
            and not _context_has_full_procedure(context_text)
        ):
            logger.info("Konteks hanya berisi daftar nama SOP, bukan rincian prosedur — jawab langsung tanpa LLM.")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            msg = "Dokumen hanya menyebutkan SOP ini sebagai salah satu item dalam daftar, namun tidak memuat rincian prosedurnya."
            if sources_text and citation_enabled:
                msg += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, msg, topic="Daftar SOP")
            yield msg
            return

        # Guard: pertanyaan meminta daftar UTUH dan dokumen memuat daftar panjang
        # yang relevan → kirim daftarnya apa adanya. Model lokal terbukti
        # memotong daftar 74 item di sekitar item ke-46, dan tidak ada cara dari
        # sisi prompt maupun konteks yang memperbaikinya (lihat
        # _build_enumeration_answer).
        jawaban_daftar = _build_enumeration_answer(context_text, resolved_query)
        if jawaban_daftar is not None:
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            full_enum_resp = jawaban_daftar
            if sources_text and citation_enabled:
                full_enum_resp += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_enum_resp, topic="Daftar SOP")
            yield jawaban_daftar
            if sources_text and citation_enabled:
                yield f"\n\n**Sumber Referensi:**\n{sources_text}"
            return

        context_text = _build_comparison_hint(context_text, resolved_query)
        context_text = _build_time_calculation_hint(context_text, resolved_query)
        context_text += _petunjuk_fokus_label(resolved_query, context_text)

        now_str = _get_current_date_info()
        is_followup = bool(chat_history and len(chat_history) > 0)
        salam_inst = (
            "   - Percakapan Lanjutan (Multi-Turn): Karena ini adalah pertanyaan lanjutan dalam percakapan yang sedang berjalan, JANGAN mengulang salam pembuka formal atau ucapan 'selamat datang'. Langsung jawab ke inti pertanyaan secara santun."
            if is_followup
            else "   - Percakapan Awal: Awali dengan salam pembuka yang sopan dan ramah (misal: 'Assalamu\\'alaikum / Halo, selamat datang di Layanan Informasi Diskominfotik Kota Banda Aceh')."
        )

        formatted_template = (
            active_prompt_template
            .replace("{current_date}", now_str)
            .replace("{salam_guide}", salam_inst)
            .replace("{institution_info}", _get_institution_info())
        )

        if "{institution_info}" not in active_prompt_template and "Profil Instansi Terkini" not in formatted_template and "Informasi Dasar Instansi" not in formatted_template:
            formatted_template = f"{formatted_template}\n\nProfil Instansi Terkini:\n{_get_institution_info()}"



        if "{context}" in formatted_template:
            system_prompt = formatted_template.replace("{context}", context_text)
        else:
            system_prompt = f"{formatted_template}\n\nKonteks Dokumen Resmi:\n{context_text}"

        is_doubt = _is_doubt_or_correction_query(query) or _is_doubt_or_correction_query(resolved_query)
        if is_doubt:
            doubt_guide = (
                "\n\nInstruksi Khusus Penanganan Keraguan & Sanggahan Pengguna:\n"
                "- Pengguna sedang menyanggah, meragukan, atau meminta penegasan atas jawaban sebelumnya.\n"
                "- Periksa dan cocokkan secara seksama dengan Konteks Dokumen Resmi di atas.\n"
                "- Jika jawaban sebelumnya SUDAH BENAR dan sesuai isi dokumen, tegaskan kembali secara santun dengan menunjukkan bukti langkah dan durasi dari dokumen (JANGAN mengubah angka atau memodifikasi rincian SOP hanya karena disanggah pengguna).\n"
                "- Jika jawaban sebelumnya terdapat kekeliruan perhitungan/salah baca dokumen, akui dan sampaikan rincian yang benar sesuai dokumen resmi secara santun.\n"
                "- DILARANG KERAS mengarang, memodifikasi durasi menit/jam, atau mengubah nama pelaksana di luar fakta dokumen."
            )
            system_prompt += doubt_guide

        estimasi_token = _estimasi_token_konteks(system_prompt)
        logger.info(
            "Jendela konteks aktif: %d token (taksiran konteks %d token / %d karakter)",
            active_num_ctx, estimasi_token, len(system_prompt),
        )

        if include_debug:
            yield {
                "type": "trace",
                "stage": "generation",
                "step": 3,
                "total_steps": 3,
                "label": "Inferensi LLM",
                "detail": f"Mengirim konteks (~{estimasi_token} token, num_ctx={active_num_ctx}) ke model {active_llm_model}...",
            }

        response_chunks = []
        for chunk in _stream_jawaban(
            system_prompt,
            resolved_query,
            temperature=temperature,
            num_ctx=active_num_ctx,
            chat_history=chat_history,
            model_name=active_llm_model,
        ):
            response_chunks.append(chunk)
            yield chunk

        if sources_text and citation_enabled:
            ref_chunk = f"\n\n**Sumber Referensi:**\n{sources_text}"
            response_chunks.append(ref_chunk)
            yield ref_chunk

        full_rag_resp = "".join(response_chunks)
        
        # Ekstrak label SOP nyata dari konteks atau sumber rujukan
        context_labels = _label_di_konteks(context_text) if context_text else []
        best_label = context_labels[0] if context_labels else ""
        if not best_label and sources_text:
            first_src = sources_text.strip().split("\n")[0].lstrip("- *# ")
            if "SOP" in first_src or "Halaman" in first_src:
                best_label = first_src

        prev_topic, prev_entity = session_memory.get_last_context(session_id)
        
        # Cek apakah query saat ini adalah meta query
        meta_words = ["hitung", "kembali", "hari apa", "kapan", "siapa", "dimana", "tadi", "lanjut", "bisa", "koreksi", "ulang"]
        is_meta_query = any(mw in query.lower() for mw in meta_words) and len(query.split()) <= 5

        if is_meta_query and prev_entity and len(prev_entity) >= 3 and not any(mw in prev_entity.lower() for mw in ["hitung", "kembali", "hari apa"]):
            active_entity = prev_entity
        else:
            active_entity = best_label or prev_entity or resolved_query

        extracted_topic = best_label or prev_topic or "Dokumen SOP"

        session_memory.add_user_message(session_id, query)
        session_memory.add_assistant_message(
            session_id,
            full_rag_resp,
            topic=extracted_topic,
            entity=active_entity,
        )

        if include_debug:
            yield {
                "type": "telemetry",
                "model_name": active_llm_model,
                "context_tokens": estimasi_token,
                "num_ctx": active_num_ctx,
                "chunks_count": len(debug_chunks),
                "is_fallback": False,
            }

        logger.info("Respons berhasil di-generate untuk session %s", session_id)

    except Exception:
        # Rincian exception ditahan di log, tidak dikirim ke pengguna: pesan
        # mentah dari Ollama/ChromaDB kerap memuat URL internal dan path berkas.
        logger.error(
            "Gagal generate respons (session=%s)",
            session_id,
            exc_info=True,
        )
        yield (
            "\n\nTerjadi kesalahan saat memproses pertanyaan Anda. "
            "Silakan coba lagi; bila berulang, hubungi administrator."
        )