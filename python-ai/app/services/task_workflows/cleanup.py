"""Perapian penanda lintas halaman setelah seluruh ekstraksi selesai."""

def tidy_document_pages(document_id: int, penyimpanan, *, logger) -> None:
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
