"""Titik masuk kompatibel untuk query MySQL dan pengaturan yang dipakai layanan.

Implementasi berada di app.repositories. Engine hanya dimiliki connection;
cache FAQ/direktori hanya dimiliki directories. Tidak ada koneksi yang dibuka
saat modul ini diimpor. Pemanggil lama tetap memakai fungsi pada path ini.
"""

from app.repositories.connection import (
    get_engine,
)
from app.repositories.documents import (
    update_document_status,
    get_all_documents,
    get_document_names,
    get_document_names_by_ids,
    get_document_by_id,
)
from app.repositories.settings import (
    get_app_setting,
    get_chatbot_rag_config,
)
from app.repositories.directories import (
    _CACHE_TTL_SECONDS,
    get_active_fast_paths,
    get_active_directories,
)
from app.repositories.document_logs import (
    record_document_log,
)
