"""Deteksi formulir SOP dan pengulangan OCR untuk kepala yang tidak lengkap."""

import logging
import re

from app.services.ocr.vision import vision_extract_general

logger = logging.getLogger("app.services.pdf_processor")

_PENANDA_FORMULIR_SOP = ("nomor sop", "nama sop", "uraian prosedur", "mutu baku")


_MIN_PENANDA_FORMULIR = 2


def _terlihat_formulir_sop(text: str) -> bool:
    """
    Apakah teks hasil OCR menunjukkan halaman berformat formulir SOP?

    Dua penanda disyaratkan, bukan satu: kata 'nama sop' saja bisa muncul di
    dokumen mana pun yang kebetulan membahas SOP, sedangkan kombinasi seperti
    'nomor sop' + 'mutu baku' praktis hanya ada pada formulirnya sendiri.
    """
    rendah = text.lower()
    return sum(p in rendah for p in _PENANDA_FORMULIR_SOP) >= _MIN_PENANDA_FORMULIR


_OCR_ULANG_MAKS = 2


_POLA_NIP = re.compile(r"\bNIP\.?\s*:?\s*\d{6,}", re.IGNORECASE)


def _kepala_sop_terlihat(text: str) -> bool:
    """Halaman ini memuat kepala formulir SOP — bukan sekadar tabel lanjutan."""
    return "nomor sop" in text.lower()


def _header_sop_tidak_lengkap(text: str) -> bool:
    """
    Kepala formulir terbaca sebagian — hasil OCR cacat dan layak diulang.

    Dua bentuk kehilangan diperiksa, keduanya hanya berlaku bila 'Nomor SOP'
    memang ada di halaman itu:

    1. 'Nama SOP' hilang — halaman kehilangan label prosedurnya, sehingga tidak
       pernah ditemukan ketika ditanya memakai nama SOP tersebut.
    2. Baris 'NIP.' hilang — sel 'Disahkan Oleh' memuat empat baris bertumpuk
       (jabatan, nama pejabat, pangkat, NIP) dan model yang menulis kepala
       sebagai daftar 'Field: nilai' hanya mengambil baris pertama. Terukur:
       dari empat kali ekstraksi halaman berkepala, tiga menjatuhkan blok itu
       dan LOLOS penjaga lama tanpa satu pun peringatan — persis kegagalan
       sunyi yang penjaga ini dibuat untuk mencegahnya, tapi hanya untuk satu
       baris yang kebetulan sudah pernah hilang lebih dulu.

    Halaman dokumen umum tidak memuat 'Nomor SOP' sama sekali, jadi keduanya
    langsung bernilai salah — tidak ada OCR ulang, tidak ada yang ditandai gagal.
    """
    if not _kepala_sop_terlihat(text):
        return False
    return "nama sop" not in text.lower() or not _POLA_NIP.search(text)


def _bagian_kepala_hilang(text: str) -> str:
    """Sebutkan bagian mana yang hilang, untuk pesan log yang bisa ditindaklanjuti."""
    kurang = []
    if "nama sop" not in text.lower():
        kurang.append("'Nama SOP'")
    if not _POLA_NIP.search(text):
        kurang.append("baris 'NIP.'")
    return " dan ".join(kurang) if kurang else "-"


def _ocr_dengan_penjaga(
    img_base64: str,
    page_label: int,
    petunjuk: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> str:
    """
    Menjalankan ekstraksi vision, mengulang bila kepala tabel SOP jelas tidak lengkap.

    Pengulangan masuk akal karena keluaran model vision tidak deterministik:
    halaman yang sama bisa menghasilkan isi berbeda tiap kali, dan percobaan
    berikutnya kerap menangkap baris yang tadi terlewat.

    Penjaganya membatasi dirinya sendiri: `_header_sop_tidak_lengkap` hanya
    bernilai benar bila 'Nomor SOP' ADA tetapi 'Nama SOP' atau baris 'NIP.'
    hilang. Halaman dokumen umum tidak memuat 'Nomor SOP' sama sekali, jadi
    langsung kembali pada percobaan pertama — tidak ada OCR ulang, tidak ada
    yang ditandai gagal.
    """
    text = vision_extract_general(
        img_base64,
        petunjuk=petunjuk,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )

    for percobaan in range(1, _OCR_ULANG_MAKS + 1):
        if not _header_sop_tidak_lengkap(text):
            return text

        logger.warning(
            "Halaman %d: kepala formulir terbaca tetapi %s hilang — OCR diulang (%d/%d)",
            page_label, _bagian_kepala_hilang(text), percobaan, _OCR_ULANG_MAKS,
        )
        ulang = vision_extract_general(
            img_base64,
            petunjuk=petunjuk,
            category_prompt=category_prompt,
            job_titles=job_titles,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

        if not _header_sop_tidak_lengkap(ulang):
            logger.info("Halaman %d: kepala formulir lengkap pada pengulangan ke-%d",
                        page_label, percobaan)
            return ulang

        # Sama-sama cacat — simpan yang paling banyak isinya.
        if len(ulang) > len(text):
            text = ulang

    logger.error(
        "Halaman %d tetap kehilangan %s setelah %d percobaan. Bila yang hilang "
        "'Nama SOP', halaman ini tidak akan mendapat label SOP dan sulit ditemukan "
        "lewat nama prosedurnya; bila yang hilang baris 'NIP.', blok pengesahan "
        "tidak akan bisa dijawab.",
        page_label, _bagian_kepala_hilang(text), _OCR_ULANG_MAKS + 1,
    )
    return text


