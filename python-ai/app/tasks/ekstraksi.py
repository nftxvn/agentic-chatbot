"""
Dua tugas Celery yang menggantikan satu tugas panjang.

`process_document_task` lama mengerjakan ekstraksi, pemotongan, dan embedding
dalam satu panggilan yang tidak bisa disela. Untuk 171 halaman pindaian itu
berjam-jam tanpa cara berhenti, dan proses yang mati di halaman 168 membuang
seluruh pekerjaannya.

Di sini pekerjaan itu dipecah pada dua batas yang berbeda sifatnya:

    ekstrak_dokumen_task   — bisa dijeda, bisa dipanggil ulang untuk melanjutkan
    potong_dan_embed_task  — hanya jalan setelah manusia menyetujui koreksinya

Di antara keduanya ada keadaan diam `menunggu_koreksi`: sistem tidak
mengerjakan apa pun sampai admin menekan tombol. Itu disengaja — hasil OCR
dokumen pindaian tidak layak masuk korpus tanpa diperiksa mata manusia.
"""

import logging

from app.services import ekstraksi_bertahap as eb
from app.tasks.process_document import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="ekstrak_dokumen_task",
    max_retries=3,
    default_retry_delay=60,
)
def ekstrak_dokumen_task(
    self,
    document_id: int,
    file_path: str,
    maks_halaman: int | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
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
    penyimpanan = eb.PenyimpananMySQL()

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
                )
                record_document_log(
                    document_id,
                    action="ocr_completed",
                    details="Ekstraksi berkas gambar berhasil melalui Vision OCR. Dokumen siap ditinjau/dikoreksi.",
                )
            except Exception:
                logger.exception("Gagal sinkron status dokumen %d ke tabel documents", document_id)
            logger.info("Dokumen gambar %d: 1 halaman terekstrak, menunggu koreksi admin", document_id)
            return {"status": eb.STATUS_MENUNGGU_KOREKSI, "halaman": 1}
        except Exception as e:
            if not penyimpanan.dokumen_ada(document_id):
                logger.info("Dokumen gambar %d telah dihapus dari sistem saat gagal ekstraksi.", document_id)
                return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

            penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, str(e))
            try:
                from app.database import update_document_status
                update_document_status(
                    document_id,
                    status="failed",
                    error_message=str(e),
                    total_pages=1,
                    processed_pages=0,
                )
            except Exception:
                logger.exception("Gagal sinkron status gagal dokumen %d ke tabel documents", document_id)
            raise self.retry(exc=e)

    import fitz
    from app.services import pdf_processor

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d tidak ditemukan di basis data saat memulai tugas Celery. Dibatalkan.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen tidak ditemukan"}

    resolved_path = pdf_processor._resolve_pdf_path(file_path)

    with fitz.open(resolved_path) as doc:
        halaman_total = len(doc)

    penyimpanan.mulai_job(document_id, halaman_total)
    try:
        from app.database import update_document_status
        update_document_status(
            document_id,
            status="processing",
            total_pages=halaman_total,
        )
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
    )

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d telah dihapus dari basis data saat ekstraksi selesai.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

    if hasil.status == eb.STATUS_SELESAI:
        _rapikan_lintas_halaman(document_id, penyimpanan)
        penyimpanan.catat_status(document_id, eb.STATUS_MENUNGGU_KOREKSI)
        try:
            from app.database import record_document_log, update_document_status
            update_document_status(
                document_id,
                status="menunggu_koreksi",
                total_pages=hasil.halaman_total,
                processed_pages=hasil.halaman_total,
            )
            record_document_log(
                document_id,
                action="ocr_completed",
                details=f"Seluruh {hasil.halaman_total} halaman berhasil diekstrak OCR. Dokumen siap ditinjau/dikoreksi.",
            )
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
            )
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
            )
        except Exception:
            logger.exception("Gagal sinkron status gagal dokumen %d ke tabel documents", document_id)

    if hasil.status == eb.STATUS_BERJALAN:
        # Batas halaman tercapai tapi pekerjaan belum tuntas — antre lagi
        # alih-alih meneruskan di tugas yang sama.
        ekstrak_dokumen_task.delay(
            document_id,
            file_path,
            maks_halaman,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

    return {
        "status": hasil.status,
        "halaman_selesai": hasil.halaman_selesai,
        "halaman_total": hasil.halaman_total,
        "pesan": hasil.pesan,
    }


def _rapikan_lintas_halaman(document_id: int, penyimpanan) -> None:
    """
    Perbaikan yang hanya mungkin setelah SELURUH halaman terkumpul.

    Penanda daftar menyeberang batas halaman: penanda pertama sebuah halaman
    hanya bisa disimpulkan dari penanda terakhir halaman sebelumnya (penerus
    `ggg` pasti `hhh`). Karena itu perbaikannya tidak bisa dijalankan per
    halaman saat ekstraksi berlangsung — ia menunggu di sini.

    Kerusakan yang diperbaikinya nyata dan sunyi: model vision tidak menghitung
    huruf berulang, ia menebak. Penanda yang memendek terbaca sebagai mundur,
    runtun daftar putus di batas halaman, dan daftar 74 item pecah jadi 59 + 15
    tanpa satu pun galat.
    """
    from app.services.pdf_processor import perbaiki_penanda_daftar

    halaman = penyimpanan.teks_terkumpul(document_id)
    diperbaiki = perbaiki_penanda_daftar(halaman)
    if not diperbaiki:
        return

    logger.info("Dokumen %d: %d penanda daftar dipulihkan", document_id, diperbaiki)
    for h in halaman:
        penyimpanan.simpan_halaman(document_id, h["page_number"], h["text"])


@celery_app.task(
    bind=True,
    name="potong_dan_embed_task",
    max_retries=3,
    default_retry_delay=60,
)
def potong_dan_embed_task(self, document_id: int, custom_kwargs: dict | None = None) -> dict:
    """
    Potong jadi induk/anak lalu simpan vektornya. Dipicu tombol admin.
    Mendukung opsi kustom dinamis untuk ukuran dan tumpang tindih chunk.
    """
    from app.database import update_document_status
    from app.services import embedding_service

    penyimpanan = eb.PenyimpananMySQL()

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

        def on_embed_progress(pct: int, msg: str) -> None:
            if not penyimpanan.dokumen_ada(document_id):
                return
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
        embedding_service.delete_document_vectors(document_id)
        tersimpan = embedding_service.embed_and_store_hierarchical(
            document_id,
            induk,
            anak,
            progress_callback=on_embed_progress,
        )
    except Exception as e:  # noqa: BLE001 - dicatat sebagai status, bukan ditelan
        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen %d telah dihapus dari basis data saat potong/embed berjalan.", document_id)
            return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

        pesan = f"Gagal memotong/embed: {type(e).__name__}: {e}"
        logger.exception("Dokumen %d gagal di tahap potong/embed", document_id)
        penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, pesan)
        raise self.retry(exc=e)

    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d telah dihapus sesudah embedding disimpan.", document_id)
        return {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"}

    penyimpanan.catat_kemajuan_embed(
        document_id,
        status=eb.STATUS_SELESAI,
        persen=100,
        pesan=f"Selesai! {tersimpan} vektor berhasil disimpan ke korpus.",
    )
    try:
        update_document_status(document_id, status="completed", total_chunks=tersimpan)
        record_document_log(
            document_id,
            action="completed",
            details=f"Dokumen berhasil diindeks ke basis pengetahuan AI ({len(induk)} parent chunks, {len(anak)} child chunks, {tersimpan} vektor).",
        )
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
