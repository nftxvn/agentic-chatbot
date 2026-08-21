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
    """
    import fitz

    from app.services import pdf_processor

    penyimpanan = eb.PenyimpananMySQL()

    with fitz.open(file_path) as doc:
        halaman_total = len(doc)

    penyimpanan.mulai_job(document_id, halaman_total)

    def ocr(nomor: int, petunjuk: str | None) -> tuple[str, str | None]:
        # Catatan format dioper masuk dan keluar. Melewatkannya tidak
        # menimbulkan galat apa pun — halaman lanjutan hanya kehilangan aturan
        # format tabelnya, dan itu baru ketahuan lewat jawaban yang ngawur.
        return pdf_processor.ekstrak_satu_halaman(file_path, nomor, petunjuk)

    hasil = eb.ekstrak_bertahap(
        document_id,
        halaman_total,
        ocr,
        penyimpanan,
        maks_halaman=maks_halaman,
    )

    if hasil.status == eb.STATUS_SELESAI:
        _rapikan_lintas_halaman(document_id, penyimpanan)
        penyimpanan.catat_status(document_id, eb.STATUS_MENUNGGU_KOREKSI)
        logger.info(
            "Dokumen %d: %d halaman terekstrak, menunggu koreksi admin",
            document_id, hasil.halaman_total,
        )
        return {"status": eb.STATUS_MENUNGGU_KOREKSI, "halaman": hasil.halaman_total}

    if hasil.status == eb.STATUS_BERJALAN:
        # Batas halaman tercapai tapi pekerjaan belum tuntas — antre lagi
        # alih-alih meneruskan di tugas yang sama.
        ekstrak_dokumen_task.delay(document_id, file_path, maks_halaman)

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
def potong_dan_embed_task(self, document_id: int) -> dict:
    """
    Potong jadi induk/anak lalu simpan vektornya. Dipicu tombol admin.

    Pemotongan dihitung ulang di sini, bukan diambil dari hasil pratinjau yang
    tersimpan. Sengaja: pratinjau bisa dilihat berjam-jam sebelum tombol
    ditekan, dan di antaranya admin mungkin menyunting halaman lagi. Potongan
    yang dihitung ulang selalu berasal dari teks yang berlaku sekarang — jadi
    mustahil ada potongan basi yang masuk korpus sementara layar menampilkan
    teks yang lain.

    Murah pula: memotong sepuluh halaman butuh sepersekian detik. Yang mahal
    adalah embedding-nya, dan itu memang hanya jalan sekali di sini.
    """
    from app.database import update_document_status
    from app.services import embedding_service

    penyimpanan = eb.PenyimpananMySQL()
    halaman = penyimpanan.teks_terkumpul(document_id)

    if not halaman:
        pesan = f"Dokumen {document_id} belum punya halaman terekstrak"
        penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, pesan)
        return {"status": eb.STATUS_GAGAL, "pesan": pesan}

    try:
        judul = embedding_service.derive_document_title(halaman)
        induk, anak = embedding_service.chunk_text_hierarchical(
            halaman, document_title=judul
        )

        # Penghapusan ditaruh sedekat mungkin dengan penyimpanan, supaya jeda
        # korpus-kosong sesingkat mungkin bila terjadi kegagalan di antaranya.
        embedding_service.delete_document_vectors(document_id)
        tersimpan = embedding_service.embed_and_store_hierarchical(
            document_id, induk, anak
        )
    except Exception as e:  # noqa: BLE001 - dicatat sebagai status, bukan ditelan
        pesan = f"Gagal memotong/embed: {type(e).__name__}: {e}"
        logger.exception("Dokumen %d gagal di tahap potong/embed", document_id)
        penyimpanan.catat_status(document_id, eb.STATUS_GAGAL, pesan)
        raise self.retry(exc=e)

    penyimpanan.catat_status(document_id, eb.STATUS_SELESAI)
    update_document_status(document_id, status="completed", total_chunks=tersimpan)

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
