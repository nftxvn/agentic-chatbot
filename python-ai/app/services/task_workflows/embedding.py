"""Workflow koreksi-ke-korpus dengan urutan progres, penghapusan, dan retry tetap."""

from app.services.document_operations import DocumentOperationCancelled

def run_embedding(
    self, document_id: int, custom_kwargs: dict | None = None,
    *, eb, logger, operation_token, operation_guard,
) -> dict:
    """
    Potong jadi induk/anak lalu simpan vektornya. Dipicu tombol admin.
    Mendukung opsi kustom dinamis untuk ukuran dan tumpang tindih chunk.
    """
    from app.database import update_document_status
    from app.services import embedding_service

    operation_guard.checkpoint()
    penyimpanan = eb.PenyimpananMySQL(operation_token=operation_token)

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d tidak ada di database saat memulai potong_dan_embed_task. Dibatalkan.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen tidak ditemukan"}

    halaman = penyimpanan.teks_terkumpul(document_id)

    if not halaman:
        pesan = f"Dokumen {document_id} belum punya halaman terekstrak"
        penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, pesan)
        return {"status": eb.STATUS_GAGAL, "pesan": pesan}

    try:
        from app.database import record_document_log, update_document_status

        penyimpanan.catat_kemajuan_embed(
            document_id,
            status=eb.STATUS_BERJALAN,
            persen=10,
            pesan="Mengumpulkan teks dokumen dan menganalisis struktur...",
        )

        judul = embedding_service.derive_document_title(halaman)
        chunk_params = custom_kwargs or {}

        penyimpanan.catat_kemajuan_embed(
            document_id,
            status=eb.STATUS_BERJALAN,
            persen=25,
            pesan="Memecah teks menjadi potongan semantik (Parent & Child)...",
        )

        induk, anak = embedding_service.chunk_text_hierarchical(
            halaman,
            document_title=judul,
            **chunk_params,
        )
        operation_guard.checkpoint()

        def on_embed_progress(pct: int, msg: str) -> None:
            if not penyimpanan.dokumen_ada(document_id):
                return
            operation_guard.checkpoint()
            penyimpanan.catat_kemajuan_embed(
                document_id,
                status=eb.STATUS_BERJALAN,
                persen=pct,
                pesan=msg,
            )

        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen %d telah dihapus sebelum embedding disimpan.", document_id)
            return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

        # Penghapusan ditaruh sedekat mungkin dengan penyimpanan, supaya jeda
        # korpus-kosong sesingkat mungkin bila terjadi kegagalan di antaranya.
        operation_guard.checkpoint()
        embedding_service.delete_document_vectors(document_id, operation_guard=operation_guard)
        tersimpan = embedding_service.embed_and_store_hierarchical(
            document_id,
            induk,
            anak,
            progress_callback=on_embed_progress,
            operation_guard=operation_guard,
        )
    except DocumentOperationCancelled:
        raise
    except Exception as e:  # noqa: BLE001 - dicatat sebagai status, bukan ditelan
        operation_guard.checkpoint()
        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen %d telah dihapus dari basis data saat potong/embed berjalan.", document_id)
            return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

        pesan = f"Gagal memotong/embed: {type(e).__name__}: {e}"
        logger.exception("Dokumen %d gagal di tahap potong/embed (retry %d/%d)", document_id, self.request.retries, self.max_retries)
        if self.request.retries >= self.max_retries:
            penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, pesan)
            try:
                from app.database import update_document_status
                update_document_status(
                    document_id,
                    status="failed",
                    error_message=pesan,
                    operation_token=operation_token,
                )
            except DocumentOperationCancelled:
                raise
            except Exception:
                logger.exception("Gagal sinkron status failed dokumen %d", document_id)
        else:
            clean_err = str(e)
            if "CUDA error" in clean_err or "CUDA_ERROR" in clean_err:
                clean_err = "Kendala GPU CUDA (alokasi memori/stream gagal)"
            elif len(clean_err) > 120:
                clean_err = clean_err[:117] + "..."

            penyimpanan.catat_kemajuan_embed(
                document_id,
                status=eb.STATUS_BERJALAN,
                persen=45,
                pesan=f"Percobaan {self.request.retries + 1}/{self.max_retries} gagal ({clean_err}), menjadwalkan ulang...",
            )
        operation_guard.checkpoint()
        raise self.retry(exc=e, kwargs={**(self.request.kwargs or {}), "_operation_token": operation_token})

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d telah dihapus sesudah embedding disimpan.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

    operation_guard.checkpoint()
    penyimpanan.catat_kemajuan_embed(
        document_id,
        status=eb.STATUS_SELESAI,
        persen=100,
        pesan=f"Selesai! {tersimpan} vektor berhasil disimpan ke korpus.",
    )
    try:
        from datetime import datetime
        update_document_status(
            document_id,
            status="completed",
            total_chunks=tersimpan,
            processed_at=datetime.utcnow(),
            operation_token=operation_token,
        )
        record_document_log(
            document_id,
            action="completed",
            details=f"Dokumen berhasil diindeks ke basis pengetahuan AI ({len(induk)} parent chunks, {len(anak)} child chunks, {tersimpan} vektor).",
            operation_token=operation_token,
        )
    except DocumentOperationCancelled:
        raise
    except Exception:
        logger.exception("Gagal sinkron status completed dokumen %d ke tabel documents", document_id)

    logger.info(
        "Dokumen %d selesai: %d induk, %d anak, %d vektor tersimpan",
        document_id, len(induk), len(anak), tersimpan,
    )
    return {
        "status": eb.STATUS_SELESAI,
        "induk": len(induk),
        "anak": len(anak),
        "vektor": tersimpan,
    }
