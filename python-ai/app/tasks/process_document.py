"""
Celery task untuk pemrosesan dokumen PDF secara asinkron.

Entry point lama tetap tersedia bagi pemanggil/worker yang menggunakannya.
Pipeline dijalankan oleh services.task_workflows.legacy; alur bertahap
memakai ekstrak_dokumen_task dan potong_dan_embed_task.
"""

import logging
from datetime import datetime

from app.celery_app import celery_app
from app.services.task_workflows import legacy, control

logger = logging.getLogger(__name__)

# Registrasi task ekstraksi bertahap
from app.tasks.ekstraksi import ekstrak_dokumen_task, potong_dan_embed_task


@celery_app.task(
    bind=True,
    name="process_document_task",
    max_retries=3,
    default_retry_delay=60,
)
def process_document_task(
    self,
    document_id: int,
    file_path: str,
    action: str,
    *,
    _operation_token: str | None = None,
) -> dict:
    """
    Task utama untuk memproses dokumen.

    Pipeline pemrosesan:
    1. Update status → 'processing'
    2. Deteksi tipe dokumen (text/scanned/mixed/spreadsheet/image)
    3. Ekstrak teks
    4. Pecah teks menjadi parent & child chunk (hierarchical)
    5. Hapus vektor lama (jika action == 'overwrite')
    6. Embed dan simpan vektor baru ke ChromaDB
    7. Update status → 'completed'

    Args:
        self: Referensi ke task instance (untuk retry).
        document_id: ID dokumen di database.
        file_path: Path absolut ke file PDF/dokumen.
        action: 'new' untuk dokumen baru, 'overwrite' untuk menimpa.

    Returns:
        Dict berisi hasil pemrosesan.
    """
    return control.run_guarded(
        document_id, _operation_token, legacy.run_legacy_document,
        self, document_id, file_path, action,
        logger=logger, datetime=datetime,
    )
