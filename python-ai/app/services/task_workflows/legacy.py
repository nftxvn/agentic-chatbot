"""Pipeline lama ekstraksi/chunking/embedding; retry dimiliki task pemanggil."""

from app.services.document_operations import DocumentOperationCancelled

def run_legacy_document(
    self, document_id: int, file_path: str, action: str,
    *, logger, datetime, operation_token, operation_guard,
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
        operation_guard.checkpoint()
        update_document_status(document_id, status="processing", operation_token=operation_token)
        logger.info("[1/7] Status dokumen %d diupdate ke 'processing'", document_id)

        # ── Langkah 2: Deteksi tipe PDF / Dokumen & Hitung Total Halaman ──
        pdf_type = document_processor.detect_document_type(file_path)
        initial_total_pages = document_processor.get_total_pages(file_path)
        operation_guard.checkpoint()
        logger.info("[2/7] Tipe dokumen: %s, Total halaman awal: %d", pdf_type, initial_total_pages)

        # ── Langkah 3: Update tipe PDF dan total halaman di database ──
        update_document_status(
            document_id,
            status="processing",
            pdf_type=pdf_type,
            total_pages=initial_total_pages,
            processed_pages=0,
            operation_token=operation_token,
        )
        logger.info("[3/7] Tipe dokumen '%s' dan total halaman %d disimpan ke database", pdf_type, initial_total_pages)

        # ── Langkah 4: Ekstrak teks dari PDF / Dokumen dengan Callback Progress ──
        from app.services.ekstraksi_bertahap import PenyimpananMySQL
        penyimpanan = PenyimpananMySQL(operation_token=operation_token)

        def on_page_progress(processed: int, total: int, page_number: int | None = None, page_text: str | None = None):
            try:
                operation_guard.checkpoint()
                update_document_status(
                    document_id,
                    status="processing",
                    total_pages=total,
                    processed_pages=processed,
                    operation_token=operation_token,
                )
                if page_number and page_text:
                    penyimpanan.simpan_halaman(document_id, page_number, page_text)
                    logger.info("Halaman %d dokumen %d langsung disimpan ke basis data", page_number, document_id)
            except DocumentOperationCancelled:
                raise
            except Exception as e:
                logger.warning("Gagal memperbarui progres/halaman dokumen %d: %s", document_id, e)

        pages = document_processor.extract_document(file_path, progress_callback=on_page_progress)
        operation_guard.checkpoint()
        total_pages = len(pages)
        logger.info("[4/7] Berhasil mengekstrak teks dari %d halaman/bagian", total_pages)

        # Ambil halaman terkumpul dari basis data (agar editan manual yang dikerjakan saat proses berjalan ikut terpakai)
        saved_pages = penyimpanan.teks_terkumpul(document_id)
        if saved_pages:
            pages = saved_pages

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
                operation_token=operation_token,
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
        operation_guard.checkpoint()
        total_chunks = len(parent_chunks)
        logger.info(
            "[5/7] Teks dipecah menjadi %d parent chunk dan %d child chunk",
            len(parent_chunks), len(child_chunks),
        )

        # ── Langkah 6: Hapus vektor lama jika overwrite ──
        if action == "overwrite":
            deleted_count = embedding_service.delete_document_vectors(document_id, operation_guard=operation_guard)
            logger.info("[6/7] Mode overwrite: %d vektor lama dihapus", deleted_count)

        # ── Langkah 7: Embed dan simpan vektor baru ──
        stored_count = embedding_service.embed_and_store_hierarchical(
            document_id, parent_chunks, child_chunks, operation_guard=operation_guard,
        )
        operation_guard.checkpoint()
        logger.info("[7/7] Berhasil menyimpan %d vektor ke ChromaDB", stored_count)

        # ── Selesai - Update status ke 'completed' ──
        update_document_status(
            document_id,
            status="completed",
            total_chunks=stored_count,
            total_pages=total_pages,
            processed_at=datetime.utcnow(),
            operation_token=operation_token,
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

    except DocumentOperationCancelled:
        raise
    except Exception as e:
        operation_guard.checkpoint()
        logger.error(
            "═══ GAGAL memproses dokumen %d: %s ═══",
            document_id,
            str(e),
            exc_info=True,
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
            operation_guard.checkpoint()
            raise self.retry(
                exc=e, countdown=60 * (retry_count + 1),
                kwargs={**(self.request.kwargs or {}), "_operation_token": operation_token},
            )

        # Sudah melebihi batas retry: Update status ke 'failed' dengan pesan error
        try:
            update_document_status(
                document_id,
                status="failed",
                error_message=str(e)[:500],  # Batasi panjang pesan error
                operation_token=operation_token,
            )
        except DocumentOperationCancelled:
            raise
        except Exception as db_err:
            logger.error(
                "Gagal mengupdate status 'failed' untuk dokumen %d: %s",
                document_id,
                str(db_err),
            )
        raise
