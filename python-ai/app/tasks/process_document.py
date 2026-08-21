"""
Celery task untuk pemrosesan dokumen PDF secara asinkron.

Task ini dipanggil oleh endpoint /api/docs/process dan menjalankan
pipeline lengkap: deteksi tipe PDF → ekstraksi teks → chunking → embedding.
"""

import logging
from datetime import datetime

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# Inisialisasi Celery app
celery_app = Celery(
    "ai_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Konfigurasi tambahan Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Acknowledge setelah task selesai (lebih aman)
    worker_prefetch_multiplier=1,  # Proses satu task pada satu waktu
)


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
    from app.database import update_document_status
    from app.services import embedding_service, document_processor

    logger.info(
        "═══ Memulai pemrosesan dokumen %d ═══ (action=%s, path=%s)",
        document_id,
        action,
        file_path,
    )

    try:
        # ── Langkah 1: Update status ke 'processing' ──
        update_document_status(document_id, status="processing")
        logger.info("[1/7] Status dokumen %d diupdate ke 'processing'", document_id)

        # ── Langkah 2: Deteksi tipe PDF / Dokumen ──
        pdf_type = document_processor.detect_document_type(file_path)
        logger.info("[2/7] Tipe dokumen terdeteksi: %s", pdf_type)

        # ── Langkah 3: Update tipe PDF di database ──
        update_document_status(document_id, status="processing", pdf_type=pdf_type)
        logger.info("[3/7] Tipe dokumen '%s' disimpan ke database", pdf_type)

        # ── Langkah 4: Ekstrak teks dari PDF / Dokumen ──
        pages = document_processor.extract_document(file_path)
        total_pages = len(pages)
        logger.info("[4/7] Berhasil mengekstrak teks dari %d halaman/bagian", total_pages)

        if not pages:
            logger.warning(
                "Dokumen %d: tidak ada teks yang bisa diekstrak", document_id
            )
            update_document_status(
                document_id,
                status="completed",
                total_chunks=0,
                total_pages=0,
                processed_at=datetime.utcnow(),
            )
            return {
                "document_id": document_id,
                "status": "completed",
                "message": "Tidak ada teks yang bisa diekstrak dari dokumen.",
                "total_pages": 0,
                "total_chunks": 0,
            }

        # ── Langkah 5: Pecah teks menjadi parent & child chunk ──
        parent_chunks, child_chunks = embedding_service.chunk_text_hierarchical(pages)
        total_chunks = len(parent_chunks)
        logger.info(
            "[5/7] Teks dipecah menjadi %d parent chunk dan %d child chunk",
            len(parent_chunks), len(child_chunks),
        )

        # ── Langkah 6: Hapus vektor lama jika overwrite ──
        if action == "overwrite":
            deleted_count = embedding_service.delete_document_vectors(document_id)
            logger.info("[6/7] Mode overwrite: %d vektor lama dihapus", deleted_count)

        # ── Langkah 7: Embed dan simpan vektor baru ──
        stored_count = embedding_service.embed_and_store_hierarchical(
            document_id, parent_chunks, child_chunks
        )
        logger.info("[7/7] Berhasil menyimpan %d vektor ke ChromaDB", stored_count)

        # ── Selesai - Update status ke 'completed' ──
        update_document_status(
            document_id,
            status="completed",
            total_chunks=stored_count,
            total_pages=total_pages,
            processed_at=datetime.utcnow(),
        )

        result = {
            "document_id": document_id,
            "status": "completed",
            "pdf_type": pdf_type,
            "total_pages": total_pages,
            "total_chunks": stored_count,
        }

        logger.info(
            "═══ Pemrosesan dokumen %d selesai ═══ (%d halaman, %d chunk)",
            document_id,
            total_pages,
            stored_count,
        )

        return result

    except Exception as e:
        logger.error(
            "═══ GAGAL memproses dokumen %d: %s ═══",
            document_id,
            str(e),
            exc_info=True,
        )

        # Update status ke 'failed' dengan pesan error
        try:
            update_document_status(
                document_id,
                status="failed",
                error_message=str(e)[:500],  # Batasi panjang pesan error
            )
        except Exception as db_err:
            logger.error(
                "Gagal mengupdate status 'failed' untuk dokumen %d: %s",
                document_id,
                str(db_err),
            )

        # Retry task jika masih ada kesempatan
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                "Mencoba retry task dokumen %d (percobaan %d/%d)...",
                document_id,
                retry_count + 1,
                self.max_retries,
            )
            raise self.retry(exc=e, countdown=60 * (retry_count + 1))

        # Sudah melebihi batas retry
        raise
