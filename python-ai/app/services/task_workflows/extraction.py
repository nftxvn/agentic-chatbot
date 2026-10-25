"""Ekstraksi bertahap; task lanjutan dan cleanup diberikan oleh entry point Celery."""

from app.services.document_operations import DocumentOperationCancelled

def run_extraction(
    self,
    document_id: int,
    file_path: str,
    maks_halaman: int | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
    *,
    eb,
    logger,
    ekstrak_dokumen_task,
    _rapikan_lintas_halaman,
    operation_token,
    operation_guard,
) -> dict:
    """
    Ekstraksi bertahap: kerjakan halaman yang belum tersimpan, lalu berhenti.

    Aman dipanggil berulang kali. Halaman yang sudah tersimpan dilewati, jadi
    "mulai" dan "lanjutkan" adalah operasi yang sama — pemanggil tidak perlu
    melacak mana yang sedang terjadi.

    Berhenti pada tiga keadaan:
      * `jeda`   — admin menekan jeda; halaman yang sedang berjalan tetap disimpan
      * `gagal`  — satu halaman tidak bisa dibaca; kemajuan sebelumnya utuh
      * `menunggu_koreksi` — semua halaman selesai, giliran manusia

    Args:
        maks_halaman: bila diisi, tugas berhenti setelah sekian halaman dan
            mengantre lagi. Berguna agar satu tugas Celery tidak berjalan
            berjam-jam — worker yang mati di tengah tugas panjang membuat
            broker mengulang seluruh tugas itu, walau halamannya sudah aman.
        category_prompt: instruksi/panduan khusus dari kategori dokumen di Laravel.
        job_titles: daftar jabatan/pelaksana relevan dari kategori dokumen.
        vision_model: model vision spesifik kategori (opsional).
        custom_prompts: kamus prompt kustom untuk menimpa aturan bawaan.
    """
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    operation_guard.checkpoint()
    penyimpanan = eb.PenyimpananMySQL(operation_token=operation_token)

    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
        from app.services import document_processor
        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen gambar %d tidak ada di basis data. Ekstraksi dibatalkan.", document_id)
            return {"status": "dibatalkan", "pesan": "Dokumen tidak ditemukan"}

        penyimpanan.mulai_job(document_id, 1)
        try:
            pages = document_processor.extract_document(
                file_path,
                category_prompt=category_prompt,
                job_titles=job_titles,
                vision_model=vision_model,
                custom_prompts=custom_prompts,
            )
            if not penyimpanan.dokumen_ada(document_id):
                logger.info("Dokumen gambar %d dihapus saat ekstraksi berjalan. Ekstraksi dihentikan.", document_id)
                return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

            operation_guard.checkpoint()

            text = pages[0]["text"] if pages else ""
            tersimpan = penyimpanan.simpan_halaman(document_id, 1, text)
            if not tersimpan:
                return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

            penyimpanan.catat_status(document_id, eb.STATUS_MENUNGGU_KOREKSI)
            try:
                from app.database import record_document_log, update_document_status
                update_document_status(
                    document_id,
                    status="menunggu_koreksi",
                    total_pages=1,
                    processed_pages=1,
                    operation_token=operation_token,
                )
                record_document_log(
                    document_id,
                    action="ocr_completed",
                    details="Ekstraksi berkas gambar berhasil melalui Vision OCR. Dokumen siap ditinjau/dikoreksi.",
                    operation_token=operation_token,
                )
            except DocumentOperationCancelled:
                raise
            except Exception:
                logger.exception("Gagal sinkron status dokumen %d ke tabel documents", document_id)
            logger.info("Dokumen gambar %d: 1 halaman terekstrak, menunggu koreksi admin", document_id)
            return {"status": eb.STATUS_MENUNGGU_KOREKSI, "halaman": 1}
        except DocumentOperationCancelled:
            raise
        except Exception as e:
            operation_guard.checkpoint()
            if not penyimpanan.dokumen_ada(document_id):
                logger.info("Dokumen gambar %d telah dihapus dari sistem saat gagal ekstraksi.", document_id)
                return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

            if self.request.retries >= self.max_retries:
                penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, str(e))
                try:
                    from app.database import update_document_status
                    update_document_status(
                        document_id,
                        status="failed",
                        error_message=str(e),
                        total_pages=1,
                        processed_pages=0,
                        operation_token=operation_token,
                    )
                except DocumentOperationCancelled:
                    raise
                except Exception:
                    logger.exception("Gagal sinkron status gagal dokumen %d ke tabel documents", document_id)
            else:
                logger.warning(
                    "Dokumen gambar %d gagal ekstraksi (percobaan %d/%d): %s. Menjadwalkan ulang...",
                    document_id, self.request.retries + 1, self.max_retries, e,
                )
            operation_guard.checkpoint()
            raise self.retry(exc=e, kwargs={**(self.request.kwargs or {}), "_operation_token": operation_token})

    import fitz
    from app.services import pdf_processor

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d tidak ditemukan di basis data saat memulai tugas Celery. Dibatalkan.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen tidak ditemukan"}

    resolved_path = pdf_processor._resolve_pdf_path(file_path)

    with fitz.open(resolved_path) as doc:
        halaman_total = len(doc)

    operation_guard.checkpoint()
    penyimpanan.mulai_job(document_id, halaman_total)
    try:
        from app.database import update_document_status
        update_document_status(
            document_id,
            status="processing",
            total_pages=halaman_total,
            operation_token=operation_token,
        )
    except DocumentOperationCancelled:
        raise
    except Exception:
        logger.exception("Gagal sinkron status processing dokumen %d ke tabel documents", document_id)

    def ocr(nomor: int, petunjuk: str | None) -> tuple[str, str | None]:
        # Catatan format dioper masuk dan keluar. Melewatkannya tidak
        # menimbulkan galat apa pun — halaman lanjutan hanya kehilangan aturan
        # format tabelnya, dan itu baru ketahuan lewat jawaban yang ngawur.
        return pdf_processor.ekstrak_satu_halaman(
            resolved_path,
            nomor,
            petunjuk,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    hasil = eb.ekstrak_bertahap(
        document_id,
        halaman_total,
        ocr,
        penyimpanan,
        maks_halaman=maks_halaman,
        check_cancelled=operation_guard.checkpoint,
    )

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d telah dihapus dari basis data saat ekstraksi selesai.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

    operation_guard.checkpoint()
    if hasil.status == eb.STATUS_SELESAI:
        _rapikan_lintas_halaman(document_id, penyimpanan)
        operation_guard.checkpoint()
        penyimpanan.catat_status(document_id, eb.STATUS_MENUNGGU_KOREKSI)
        try:
            from app.database import record_document_log, update_document_status
            update_document_status(
                document_id,
                status="menunggu_koreksi",
                total_pages=hasil.halaman_total,
                processed_pages=hasil.halaman_total,
                operation_token=operation_token,
            )
            record_document_log(
                document_id,
                action="ocr_completed",
                details=f"Seluruh {hasil.halaman_total} halaman berhasil diekstrak OCR. Dokumen siap ditinjau/dikoreksi.",
                operation_token=operation_token,
            )
        except DocumentOperationCancelled:
            raise
        except Exception:
            logger.exception("Gagal sinkron status dokumen %d ke tabel documents", document_id)
        logger.info(
            "Dokumen %d: %d halaman terekstrak, menunggu koreksi admin",
            document_id, hasil.halaman_total,
        )
        return {"status": eb.STATUS_MENUNGGU_KOREKSI, "halaman": hasil.halaman_total}

    if hasil.status == eb.STATUS_JEDA:
        try:
            from app.database import update_document_status
            update_document_status(
                document_id,
                status="paused",
                total_pages=hasil.halaman_total,
                processed_pages=hasil.halaman_selesai,
                operation_token=operation_token,
            )
        except DocumentOperationCancelled:
            raise
        except Exception:
            logger.exception("Gagal sinkron status jeda dokumen %d ke tabel documents", document_id)

    if hasil.status == eb.STATUS_GAGAL:
        try:
            from app.database import update_document_status
            update_document_status(
                document_id,
                status="failed",
                error_message=hasil.pesan,
                total_pages=hasil.halaman_total,
                processed_pages=hasil.halaman_selesai,
                operation_token=operation_token,
            )
        except DocumentOperationCancelled:
            raise
        except Exception:
            logger.exception("Gagal sinkron status gagal dokumen %d ke tabel documents", document_id)

    if hasil.status == eb.STATUS_BERJALAN:
        # Batas halaman tercapai tapi pekerjaan belum tuntas — antre lagi
        # alih-alih meneruskan di tugas yang sama.
        operation_guard.checkpoint()
        ekstrak_dokumen_task.delay(
            document_id,
            file_path,
            maks_halaman,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
            _operation_token=operation_token,
        )

    return {
        "status": hasil.status,
        "halaman_selesai": hasil.halaman_selesai,
        "halaman_total": hasil.halaman_total,
        "pesan": hasil.pesan,
    }
