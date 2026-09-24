"""
Service untuk embedding teks dan penyimpanan vektor di ChromaDB.
Menggunakan SentenceTransformer untuk menghasilkan embedding
dan ChromaDB sebagai vector store persisten.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

import chromadb
from chromadb.api.models.Collection import Collection
# Diberi alias: nama aslinya "Settings" bentrok dengan settings konfigurasi
# aplikasi yang diimpor di bawah.
from chromadb.config import Settings as ChromaSettings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Diimpor SEBELUM sentence_transformers dengan sengaja, melanggar urutan
# abjad yang biasa. app.config-lah yang memuat .env, dan huggingface_hub
# membaca HF_HUB_OFFLINE sekali saja saat diimpor — kalau urutannya dibalik,
# setelan itu tidak akan pernah terbaca.
from app.config import settings  # noqa: I001

from sentence_transformers import CrossEncoder, SentenceTransformer

logger = logging.getLogger(__name__)

# Variabel global untuk lazy loading (singleton pattern)
_embedding_model: SentenceTransformer | None = None
_reranker_model: CrossEncoder | None = None

_chroma_collection: Collection | None = None

# Nama koleksi di ChromaDB
_COLLECTION_NAME = "documents"


# Perangkat tempat bge-m3 dijalankan. Lihat EMBEDDING_DEVICE di config.py untuk
# alasan dan kapan perlu diubah.
#
# None diserahkan ke SentenceTransformer, yang berarti auto-detect (CUDA bila
# tersedia) — perilaku bawaan pustakanya.
_EMBEDDING_DEVICE = (
    None if settings.EMBEDDING_DEVICE.strip().lower() == "auto"
    else settings.EMBEDDING_DEVICE.strip().lower()
)


def get_embedding_model(local_only: bool = True) -> SentenceTransformer | None:
    """
    Mendapatkan model SentenceTransformer (lazy loading).
    
    Args:
        local_only: Bila True, hanya mencoba memuat dari disk cache lokal tanpa mengunduh dari internet.
                    Bila model belum terunduh, langsung return None agar bisa dialihkan ke Ollama.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    # 1. Coba muat dari cache lokal terlebih dahulu (cepat, tanpa blocking download)
    try:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=_EMBEDDING_DEVICE,
            local_files_only=True,
        )
        logger.info(
            "Model embedding SentenceTransformer berhasil dimuat dari disk cache lokal: %s (%s)",
            settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DEVICE,
        )
        return _embedding_model
    except Exception:
        pass

    if local_only:
        return None

    # 2. Jika local_only=False (Ollama tidak tersedia), baru lakukan unduhan online
    logger.info(
        "Memuat/mengunduh model embedding online: %s di %s ...",
        settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DEVICE,
    )
    try:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=_EMBEDDING_DEVICE,
            local_files_only=False,
        )
        logger.info("Model embedding SentenceTransformer berhasil diunduh dan dimuat")
        return _embedding_model
    except Exception as e:                                      # noqa: BLE001
        if type(e).__name__ == "OfflineModeIsEnabled":
            os.environ.pop("HF_HUB_OFFLINE", None)
            konstanta = sys.modules.get("huggingface_hub.constants")
            if konstanta is not None:
                konstanta.HF_HUB_OFFLINE = False
            try:
                _embedding_model = SentenceTransformer(
                    settings.EMBEDDING_MODEL_NAME,
                    device=_EMBEDDING_DEVICE,
                    local_files_only=False,
                )
                return _embedding_model
            except Exception as retry_err:
                logger.warning("Gagal memuat SentenceTransformer setelah reset luring: %s", retry_err)
                return None
        logger.warning("Gagal mengunduh model SentenceTransformer (%s): %s", settings.EMBEDDING_MODEL_NAME, e)
        return None


def _get_available_ollama_models() -> list[str]:
    """Cek daftar model yang terpasang di Ollama secara dinamis."""
    import requests
    try:
        res = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            return [m.get("name", "") for m in models_data if m.get("name")]
    except Exception:
        pass
    return []


def _encode_via_ollama(texts: list[str]) -> list[list[float]]:
    """
    Fallback embedding menggunakan Ollama API di host bila model lokal belum terunduh.
    Mencari model embedding bge-m3, nomic-embed-text, atau LLM aktif dari Ollama tags.
    Menggunakan batching agar efisien dan tidak timeout.
    """
    import requests

    if not texts:
        return []

    installed = _get_available_ollama_models()
    
    # Prioritaskan model khusus embedding yang terpasang di Ollama
    candidate_order = ["bge-m3", "bge", "nomic-embed-text", "all-minilm", settings.LLM_MODEL_NAME, "qwen2.5:7b", "qwen3:8b"]
    
    selected_models: list[str] = []
    for cand in candidate_order:
        for inst in installed:
            if cand in inst.lower() and inst not in selected_models:
                selected_models.append(inst)
    
    for cand in candidate_order:
        if cand not in selected_models:
            selected_models.append(cand)

    batch_size = 25
    for m_name in selected_models:
        all_embeddings = []
        success = True
        
        # 1. Coba endpoint batch /api/embed (Ollama v0.1.34+)
        try:
            for i in range(0, len(texts), batch_size):
                chunk = texts[i : i + batch_size]
                res = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embed",
                    json={"model": m_name, "input": chunk},
                    timeout=60,
                )
                if res.status_code == 200:
                    data = res.json()
                    embs = data.get("embeddings", [])
                    if embs and len(embs) == len(chunk):
                        all_embeddings.extend(embs)
                    else:
                        success = False
                        break
                else:
                    success = False
                    break
                    
            if success and len(all_embeddings) == len(texts):
                logger.info("Berhasil membuat %d embeddings via Ollama /api/embed (model: %s)", len(texts), m_name)
                return all_embeddings
        except Exception:
            pass

        # 2. Coba endpoint single /api/embeddings jika /api/embed tidak merespon
        try:
            all_embeddings = []
            for t in texts:
                res = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": m_name, "prompt": t},
                    timeout=30,
                )
                if res.status_code == 200:
                    emb = res.json().get("embedding", [])
                    if emb:
                        all_embeddings.append(emb)
                    else:
                        break
                else:
                    break
            if len(all_embeddings) == len(texts):
                logger.info("Berhasil membuat %d embeddings via Ollama /api/embeddings (model: %s)", len(texts), m_name)
                return all_embeddings
        except Exception:
            continue

    raise RuntimeError("Ollama embedding tidak merespon atau model tidak cocok.")


def encode_texts(texts: list[str]) -> list[list[float]]:
    """
    Menghasilkan embedding vektor dari daftar teks.
    Prioritas:
      1. Ollama Embedding di host (GPU-accelerated di host, ultra-cepat 0.05s).
      2. Model SentenceTransformer dari cache lokal disk.
      3. Unduh model SentenceTransformer online (fallback terakhir).
    """
    if not texts:
        return []

    # 1. Prioritas Utama: Coba via Ollama di host (GPU-accelerated)
    try:
        return _encode_via_ollama(texts)
    except Exception:
        pass

    # 2. Coba dari cache lokal disk
    model = get_embedding_model(local_only=True)
    if model is not None:
        try:
            return model.encode(texts, show_progress_bar=False).tolist()
        except Exception as e:
            logger.warning("Eksekusi SentenceTransformer lokal gagal (%s).", e)

    # 3. Fallback: Unduh SentenceTransformer online
    model_online = get_embedding_model(local_only=False)
    if model_online is not None:
        return model_online.encode(texts, show_progress_bar=False).tolist()

    raise RuntimeError("Gagal menghasilkan embedding: Ollama tidak merespon, cache lokal tidak ada, dan unduhan online gagal.")


def encode_query(query: str) -> list[float]:
    """
    Menghasilkan 1D embedding vektor untuk satu kalimat query pencarian.
    """
    embs = encode_texts([query])
    if embs:
        return embs[0]
    return []


def get_reranker_model() -> CrossEncoder | None:
    """
    Mendapatkan model CrossEncoder Reranker (lazy loading).
    Model hanya dimuat sekali saat pertama kali dipanggil.
    Dijalankan di CPU (device='cpu') agar 100% VRAM GPU tetap dialokasikan
    penuh untuk LLM tanpa OOM.

    Bila model belum terunduh atau gagal dimuat, fungsi ini aman mengembalikan None
    dan sistem RAG secara otomatis beralih ke ranking RRF (Reciprocal Rank Fusion)
    standar tanpa galat dan tanpa jeda.
    """
    global _reranker_model
    if not settings.RERANKER_ENABLED:
        return None
    if _reranker_model is not None:
        return _reranker_model

    # 1. Coba muat dari cache lokal terlebih dahulu (cepat, tanpa hanging)
    try:
        _reranker_model = CrossEncoder(
            settings.RERANKER_MODEL_NAME,
            device=settings.RERANKER_DEVICE,
            local_files_only=True,
        )
        logger.info("Model Reranker berhasil dimuat dari disk cache: %s", settings.RERANKER_MODEL_NAME)
        return _reranker_model
    except Exception:
        pass

    # 2. Coba unduh/muat online dengan penanganan galat aman
    logger.info(
        "Memuat model Reranker: %s di %s ...",
        settings.RERANKER_MODEL_NAME, settings.RERANKER_DEVICE,
    )
    try:
        _reranker_model = CrossEncoder(
            settings.RERANKER_MODEL_NAME,
            device=settings.RERANKER_DEVICE,
            local_files_only=False,
        )
        logger.info("Model Reranker berhasil dimuat di %s", settings.RERANKER_DEVICE)
        return _reranker_model
    except Exception as e:                                      # noqa: BLE001
        logger.warning(
            "Model Reranker (%s) tidak tersedia (%s). RAG berjalan optimal dengan RRF standar.",
            settings.RERANKER_MODEL_NAME, e,
        )
        _reranker_model = None

    return _reranker_model


def get_chroma_collection() -> Collection:
    """
    Mendapatkan koleksi ChromaDB (lazy loading).
    Client dan koleksi hanya dibuat sekali saat pertama kali dipanggil.

    Returns:
        Koleksi ChromaDB 'documents'.
    """
    global _chroma_collection
    if _chroma_collection is None:
        logger.info(
            "Menginisialisasi ChromaDB di: %s", settings.CHROMA_PERSIST_DIR
        )
        # Matikan telemetri anonim ChromaDB: tidak ada data pemakaian yang
        # dikirim keluar dari mesin ini. Efeknya, chromadb menyetel
        # posthog.disabled = True (chromadb/telemetry/product/posthog.py:17).
        #
        # CATATAN — ini TIDAK menghilangkan baris error di log. chromadb 0.5.5
        # memanggil posthog.capture() dengan 3 argumen posisional, sedangkan
        # posthog 7.x hanya menerima 1, sehingga TypeError terjadi saat
        # pemanggilan — sebelum pengecekan `disabled` di dalam fungsi sempat
        # dijalankan. Kebisingan "Failed to send telemetry event ..." karena
        # itu diredam di level logging (lihat app/main.py), bukan di sini.
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Gunakan cosine similarity
        )
        logger.info(
            "Koleksi ChromaDB '%s' siap (total: %d chunk vektor)",
            _COLLECTION_NAME,
            _chroma_collection.count(),
        )
    return _chroma_collection




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
    for item in raw_items:
        if current and len(current) + len(item) + 1 > max_size:
            out.append(current)
            current = item
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


# ── Penanda versi korpus (dibaca lintas proses) ──────────────────
#
# Ingest berjalan di proses pekerja Celery, sedangkan cache BM25 hidup di proses
# server FastAPI. Memanggil invalidate_bm25_cache() dari Celery hanya
# membersihkan cache milik proses Celery: variabel level modul tidak menyeberangi
# batas proses, jadi cache di server API sama sekali tidak tersentuh.
#
# Satu-satunya penanda yang selama ini menyelamatkan adalah collection.count(),
# dan itu tidak cukup — menimpa dokumen dengan jumlah potongan yang kebetulan
# sama membuat count tidak berubah, sehingga server API terus menyajikan teks
# dokumen versi lama sampai di-restart.
#
# Penanda ditulis sebagai berkas di dalam direktori ChromaDB, satu-satunya
# tempat yang sudah pasti dipakai bersama oleh kedua proses.
_CORPUS_VERSION_FILE = "corpus_version.txt"


def _corpus_version_path() -> Path:
    """Lokasi berkas penanda, di dalam direktori persist ChromaDB."""
    return Path(settings.CHROMA_PERSIST_DIR) / _CORPUS_VERSION_FILE


def read_corpus_version() -> str:
    """
    Membaca penanda versi korpus.

    Mengembalikan string kosong bila penandanya belum pernah ditulis atau tidak
    terbaca. Keduanya diperlakukan sama — "tidak diketahui" — sehingga pemanggil
    tetap jatuh kembali ke collection.count() seperti perilaku sebelumnya.
    """
    try:
        return _corpus_version_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def bump_corpus_version() -> str:
    """
    Menaikkan penanda versi korpus supaya proses lain tahu isinya sudah berubah.

    Memakai time.time_ns() sebagai nilai: cukup untuk membedakan dua ingest yang
    berdekatan tanpa perlu menyimpan hitungan di mana pun.
    """
    version = str(time.time_ns())

    try:
        path = _corpus_version_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version, encoding="utf-8")
    except OSError as e:
        # Ingest tidak boleh gagal hanya karena penanda tidak bisa ditulis.
        logger.warning("Gagal menulis penanda versi korpus: %s", e)
        return ""

    return version


def _invalidate_search_index() -> None:
    """
    Memberi tahu bahwa korpus berubah, supaya indeks BM25 yang di-cache dibangun
    ulang pada query berikutnya.

    Dua langkah, karena masing-masing menjangkau sasaran yang berbeda:

    1. bump_corpus_version() menulis penanda ke disk — inilah yang terbaca oleh
       proses LAIN, yaitu server FastAPI saat ingest berjalan di pekerja Celery.
    2. invalidate_bm25_cache() membersihkan cache di proses ini sendiri, untuk
       kasus ingest dan chat kebetulan berjalan dalam satu proses (skrip uji).

    Import pada langkah 2 sengaja di dalam fungsi: rag_service sudah mengimpor
    modul ini, jadi import di level modul akan melingkar.
    """
    bump_corpus_version()

    try:
        from app.services.rag_service import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception as e:  # jangan sampai ingest gagal hanya karena invalidasi
        logger.warning("Gagal invalidasi cache BM25: %s", e)


def delete_document_vectors(document_id: int) -> int:
    """
    Menghapus semua vektor yang terkait dengan document_id dari ChromaDB.

    Args:
        document_id: ID dokumen yang vektornya akan dihapus.

    Returns:
        Jumlah vektor yang dihapus.
    """
    collection = get_chroma_collection()

    try:
        # Cari semua ID yang terkait dengan document_id
        results = collection.get(
            where={"document_id": document_id},
        )

        existing_ids = results["ids"]
        count = len(existing_ids)

        if count > 0:
            collection.delete(ids=existing_ids)
            _invalidate_search_index()
            logger.info(
                "Berhasil menghapus %d vektor untuk dokumen %d",
                count,
                document_id,
            )
        else:
            logger.info("Tidak ada vektor yang ditemukan untuk dokumen %d", document_id)

        return count

    except Exception as e:
        logger.error(
            "Gagal menghapus vektor untuk dokumen %d: %s",
            document_id,
            str(e),
        )
        raise



def get_document_chunks(document_id: int) -> list[dict]:
    """
    Mengambil semua chunk teks yang tersimpan di ChromaDB untuk dokumen tertentu.
    
    Args:
        document_id: ID dokumen sumber.
        
    Returns:
        List of dict berisi chunk data.
    """
    collection = get_chroma_collection()
    try:
        results = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"]
        )
        
        chunks = []
        if results and results.get("ids"):
            for i in range(len(results["ids"])):
                chunks.append({
                    "id": results["ids"][i],
                    "text": results["documents"][i],
                    "metadata": results["metadatas"][i]
                })
                
        # Urutkan berdasarkan chunk_index agar berurutan
        chunks.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
        return chunks
    except Exception as e:
        logger.error("Gagal mengambil chunk dari ChromaDB (dokumen %d): %s", document_id, str(e))
        return []


def embed_and_store_hierarchical(
    document_id: int,
    parent_chunks: list[dict],
    child_chunks: list[dict],
    progress_callback: Callable[[int, str], None] | None = None,
) -> int:
    """
    Menyimpan parent dan child chunks ke ChromaDB.

    - Child chunks: di-embed untuk pencarian semantik (metadata: chunk_type="child")
    - Parent chunks: di-embed dan disimpan untuk konteks LLM (metadata: chunk_type="parent")
    - Setiap child memiliki metadata 'parent_id' yang menunjuk ke parent-nya.

    Args:
        document_id: ID dokumen sumber.
        parent_chunks: List parent chunks dari chunk_text_hierarchical().
        child_chunks: List child chunks dari chunk_text_hierarchical().
        progress_callback: Callback opsional (persen: int, pesan: str) untuk progres live.

    Returns:
        Jumlah total vektor yang berhasil disimpan (parent + child).
    """
    if not child_chunks:
        logger.warning("Tidak ada chunk untuk di-embed (dokumen %d)", document_id)
        return 0

    if progress_callback:
        progress_callback(35, "Menyiapkan mesin embedding vektor...")

    collection = get_chroma_collection()

    try:
        batch_size = 50

        # ── Simpan Parent Chunks ──
        parent_texts: list[str] = []
        parent_ids: list[str] = []
        parent_metadatas: list[dict[str, Any]] = []

        for c in parent_chunks:
            pid = f"doc_{document_id}_parent_{c['chunk_index']}"
            parent_ids.append(pid)
            parent_texts.append(c["text"])
            parent_metadatas.append({
                "document_id": document_id,
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "chunk_type": "parent",
            })

        if progress_callback:
            progress_callback(45, f"Menghitung embedding {len(parent_texts)} potongan induk...")

        logger.info(
            "Menghasilkan embedding untuk %d parent chunks (dokumen %d)...",
            len(parent_texts), document_id,
        )
        parent_embeddings = encode_texts(parent_texts)

        for i in range(0, len(parent_ids), batch_size):
            end = min(i + batch_size, len(parent_ids))
            collection.upsert(
                ids=parent_ids[i:end],
                embeddings=parent_embeddings[i:end],
                documents=parent_texts[i:end],
                metadatas=parent_metadatas[i:end],
            )

        logger.info("Disimpan %d parent chunks (dokumen %d)", len(parent_ids), document_id)

        # ── Simpan Child Chunks ──
        child_texts: list[str] = []
        child_ids: list[str] = []
        child_metadatas: list[dict[str, Any]] = []

        for c in child_chunks:
            cid = f"doc_{document_id}_child_{c['chunk_index']}"
            child_ids.append(cid)
            child_texts.append(c["text"])
            child_metadatas.append({
                "document_id": document_id,
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "chunk_type": "child",
                "parent_id": f"doc_{document_id}_parent_{c['parent_index']}",
            })

        total_children = len(child_texts)
        child_embeddings: list[list[float]] = []

        for i in range(0, total_children, batch_size):
            end = min(i + batch_size, total_children)
            batch_texts = child_texts[i:end]
            if progress_callback:
                pct = 55 + int((i / max(1, total_children)) * 35)
                progress_callback(pct, f"Menghitung embedding potongan anak ({end}/{total_children})...")
            batch_emb = encode_texts(batch_texts)
            collection.upsert(
                ids=child_ids[i:end],
                embeddings=batch_emb,
                documents=batch_texts,
                metadatas=child_metadatas[i:end],
            )

        if progress_callback:
            progress_callback(95, "Memperbarui indeks pencarian ChromaDB...")

        logger.info("Disimpan %d child chunks (dokumen %d)", len(child_ids), document_id)

        _invalidate_search_index()

        total = len(parent_ids) + len(child_ids)
        if progress_callback:
            progress_callback(100, f"Selesai! {total} vektor berhasil disimpan.")

        logger.info(
            "Total %d vektor hierarchical disimpan ke ChromaDB (dokumen %d)",
            total, document_id,
        )
        return total

    except Exception as e:
        logger.error(
            "Gagal menyimpan hierarchical chunks (dokumen %d): %s",
            document_id, str(e),
        )
        raise
