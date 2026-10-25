"""Penanda korpus lintas proses dan invalidasi cache pencarian pada proses ini."""

import logging
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger("app.services.embedding_service")

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
