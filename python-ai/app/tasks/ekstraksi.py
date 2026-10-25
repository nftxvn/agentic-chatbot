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
from app.celery_app import celery_app
from app.services.task_workflows import extraction, cleanup, embedding, control

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
    *,
    _operation_token: str | None = None,
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
    return control.run_guarded(
        document_id, _operation_token, extraction.run_extraction,
        self, document_id, file_path, maks_halaman, category_prompt,
        job_titles, vision_model, custom_prompts,
        eb=eb, logger=logger,
        ekstrak_dokumen_task=ekstrak_dokumen_task,
        _rapikan_lintas_halaman=_rapikan_lintas_halaman,
    )


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
    return cleanup.tidy_document_pages(document_id, penyimpanan, logger=logger)


@celery_app.task(
    bind=True,
    name="potong_dan_embed_task",
    max_retries=3,
    default_retry_delay=60,
)
def potong_dan_embed_task(
    self, document_id: int, custom_kwargs: dict | None = None,
    *, _operation_token: str | None = None,
) -> dict:
    """
    Potong jadi induk/anak lalu simpan vektornya. Dipicu tombol admin.
    Mendukung opsi kustom dinamis untuk ukuran dan tumpang tindih chunk.
    """
    return control.run_guarded(
        document_id, _operation_token, embedding.run_embedding,
        self, document_id, custom_kwargs, eb=eb, logger=logger,
    )
