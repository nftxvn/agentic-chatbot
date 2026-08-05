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
    Task utama untuk memproses dokumen PDF.

    Pipeline pemrosesan:
    1. Update status → 'processing'
    2. Deteksi tipe PDF (text/scanned/mixed)
    3. Ekstrak teks (dengan OCR jika diperlukan)
    4. Pecah teks menjadi chunk
    5. Hapus vektor lama (jika action == 'overwrite')
    6. Embed dan simpan vektor baru ke ChromaDB
    7. Update status → 'completed'

    Args:
        self: Referensi ke task instance (untuk retry).
        document_id: ID dokumen di database.
        file_path: Path absolut ke file PDF.
        action: 'new' untuk dokumen baru, 'overwrite' untuk menimpa.

    Returns:
        Dict berisi hasil pemrosesan.
    """
    # Import di sini untuk menghindari circular imports
    from app.database import update_document_status
    from app.services import embedding_service, pdf_processor

    logger.info(
        "═══ Memulai pemrosesan dokumen %d ═══ (action=%s, path=%s)",
        document_id,
        action,
        file_path,
    )

        # Import di sini untuk menghindari circular imports
        import fitz
        from app.database import get_document_by_id, update_document_status
        from app.services import embedding_service, pdf_processor

        # ── Langkah 1: Update status ke 'processing' ──
        update_document_status(document_id, status="processing")
        logger.info("[1/5] Status dokumen %d diupdate ke 'processing'", document_id)

        # ── Langkah 2: Deteksi tipe PDF ──
        pdf_type = pdf_processor.detect_pdf_type(file_path)
        update_document_status(document_id, status="processing", pdf_type=pdf_type)
        logger.info("[2/5] Tipe PDF '%s' disimpan ke database", pdf_type)

        # ── Langkah 3: Hapus vektor lama jika overwrite ──
        if action == "overwrite":
            deleted_count = embedding_service.delete_document_vectors(document_id)
            logger.info("[3/5] Mode overwrite: %d vektor lama dihapus", deleted_count)

        # ── Langkah 4: Pemrosesan Streaming Halaman per Halaman ──
        doc = fitz.open(file_path)
        total_pages = len(doc)
        total_accumulated_chunks = 0

        logger.info("[4/5] Memulai pemrosesan streaming %d halaman PDF...", total_pages)

        for page_idx in range(total_pages):
            page_num = page_idx + 1

            # Cek apakah admin membatalkan / menunda pemrosesan di tengah jalan
            current_doc = get_document_by_id(document_id)
            if current_doc and current_doc.get("status") in ["failed", "paused"]:
                logger.info(
                    "Pemrosesan dokumen %d dihentikan (status saat ini: %s)",
                    document_id,
                    current_doc.get("status"),
                )
                doc.close()
                return {
                    "document_id": document_id,
                    "status": current_doc.get("status"),
                    "message": "Pemrosesan dihentikan oleh admin.",
                }

            page = doc[page_idx]
            page_content = pdf_processor.process_single_page(page, page_num)

            if page_content and page_content.get("text"):
                page_chunks = embedding_service.chunk_text([page_content])
                if page_chunks:
                    stored_count = embedding_service.embed_and_store(document_id, page_chunks)
                    total_accumulated_chunks += stored_count

            # Update progres halaman & total chunks ke database secara real-time
            update_document_status(
                document_id,
                status="processing",
                total_pages=total_pages,
                total_chunks=total_accumulated_chunks,
            )
            logger.info(
                "Progres Halaman %d/%d (Total Chunks: %d)",
                page_num,
                total_pages,
                total_accumulated_chunks,
            )

        doc.close()

        # ── Langkah 5: Selesai - Update status ke 'completed' ──
        update_document_status(
            document_id,
            status="completed",
            total_chunks=total_accumulated_chunks,
            total_pages=total_pages,
            processed_at=datetime.utcnow(),
        )

        result = {
            "document_id": document_id,
            "status": "completed",
            "pdf_type": pdf_type,
            "total_pages": total_pages,
            "total_chunks": total_accumulated_chunks,
        }

        logger.info(
            "═══ Pemrosesan dokumen %d selesai ═══ (%d halaman, %d chunk)",
            document_id,
            total_pages,
            total_accumulated_chunks,
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
