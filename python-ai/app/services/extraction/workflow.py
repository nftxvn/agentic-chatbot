"""Orkestrasi simpan-per-halaman, jeda kooperatif, resume, dan flush cache."""

import logging
import time
from typing import Callable

from app.services.document_operations import DocumentOperationCancelled

from app.services.extraction.contracts import (
    Kemajuan,
    Penyimpanan,
    STATUS_BERJALAN,
    STATUS_GAGAL,
    STATUS_JEDA,
    STATUS_SELESAI,
)

logger = logging.getLogger("app.services.ekstraksi_bertahap")

# Batas interval halaman untuk membersihkan prompt/KV cache Ollama di RAM.
# Angka 12 halaman (~1.9 GB cache) memaksimalkan pemakaian RAM tanpa menyentuh
# batas kritis (thrashing/OOM).
_FLUSH_CACHE_INTERVAL = 12


def flush_ollama_cache(model_name: str | None = None) -> None:
    """
    Membebaskan akumulasi prompt/KV cache Ollama dari RAM/VRAM.

    Ollama menimbun prompt cache per halaman hingga batas 8 GB. Pada batch
    ekstraksi gambar, cache halaman lama tidak pernah terpakai lagi.
    Mengirim keep_alive: 0 mengosongkan timbunan cache tersebut dan menjaga
    kecepatan inferensi stabil di ~11-12 t/s.
    """
    try:
        import requests
        from app.config import settings
        from app.services.pdf_processor import resolve_vision_model

        target_model = resolve_vision_model(model_name)
        requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={"model": target_model, "keep_alive": 0},
            timeout=5,
        )
        logger.info("Prompt cache Ollama (%s) berhasil dibersihkan (VRAM/RAM dilepas).", target_model)
    except Exception as e:
        logger.warning("Gagal flush cache Ollama: %s", e)


def ekstrak_bertahap(
    document_id: int,
    halaman_total: int,
    ocr_satu_halaman: Callable[[int, str | None], tuple[str, str | None]],
    penyimpanan: Penyimpanan,
    *,
    maks_halaman: int | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Kemajuan:
    """
    Kerjakan halaman yang belum tersimpan, satu per satu, sampai selesai atau dijeda.

    Argumen:
        halaman_total: jumlah halaman dokumen. Dipakai untuk persentase dan
            untuk tahu kapan pekerjaan benar-benar tuntas.
        ocr_satu_halaman: fungsi (nomor, catatan) -> (teks, catatan_baru) untuk
            SATU halaman (1-indeks). Disuntikkan, bukan dipanggil langsung,
            supaya alur ini bisa diuji tanpa Ollama — dan supaya pemanggil
            bebas memilih jalur ekstraksi.
            Catatan formatnya dibaca dari penyimpanan sebelum halaman pertama
            dan disimpan kembali sesudah tiap halaman, sehingga ia bertahan
            melewati jeda maupun worker yang mati di tengah jalan.
        maks_halaman: batas halaman per putaran. Berguna bila pemanggil ingin
            memotong pekerjaan jadi beberapa tugas Celery pendek alih-alih satu
            tugas panjang.

    Melanjutkan otomatis: halaman yang sudah tersimpan dilewati, jadi memanggil
    fungsi ini berulang kali aman dan selalu meneruskan dari yang terakhir.
    """
    def checkpoint():
        if check_cancelled is not None:
            check_cancelled()

    def flush_cache():
        checkpoint()
        flush_ollama_cache()

    mulai = time.perf_counter()
    checkpoint()

    # Periksa apakah dokumen masih ada di basis data
    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d tidak ditemukan di basis data saat mulai ekstraksi bertahap.", document_id)
        return Kemajuan(
            document_id, STATUS_GAGAL, halaman_total, 0,
            pesan="Dokumen tidak ditemukan di basis data.",
        )

    sudah = penyimpanan.halaman_tersimpan(document_id)
    tersisa = [n for n in range(1, halaman_total + 1) if n not in sudah]

    if not tersisa:
        penyimpanan.catat_status(document_id, STATUS_SELESAI)
        return Kemajuan(document_id, STATUS_SELESAI, halaman_total, halaman_total)

    # Diperiksa SEBELUM halaman pertama juga: pengguna bisa menekan jeda saat
    # tugas masih mengantre di Celery, dan permintaan itu harus tetap dihormati.
    if penyimpanan.jeda_diminta(document_id):
        penyimpanan.catat_status(document_id, STATUS_JEDA)
        return Kemajuan(document_id, STATUS_JEDA, halaman_total, len(sudah))

    penyimpanan.catat_status(document_id, STATUS_BERJALAN)
    petunjuk = penyimpanan.baca_petunjuk(document_id)
    diproses: list[int] = []

    for nomor in tersisa:
        checkpoint()
        if maks_halaman is not None and len(diproses) >= maks_halaman:
            break

        # 1. Periksa apakah dokumen masih ada sebelum membuang 20-60 detik waktu inferensi vision
        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen %d telah dihapus dari sistem. Menghentikan ekstraksi bertahap.", document_id)
            flush_cache()
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
                pesan="Dokumen telah dihapus dari sistem.",
            )

        # 2. Periksa permintaan jeda SEBELUM memulai OCR halaman berikutnya
        if penyimpanan.jeda_diminta(document_id):
            penyimpanan.catat_status(document_id, STATUS_JEDA)
            penyimpanan.batalkan_jeda(document_id)
            flush_cache()
            return Kemajuan(
                document_id, STATUS_JEDA, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
            )

        try:
            teks, petunjuk = ocr_satu_halaman(nomor, petunjuk)
            checkpoint()
        except DocumentOperationCancelled:
            raise
        except Exception as e:  # noqa: BLE001 - dicatat sebagai status, bukan ditelan
            checkpoint()
            # Jika dokumen telah dihapus saat inferensi berlangsung, keluar secara bersih
            if not penyimpanan.dokumen_ada(document_id):
                logger.info("Dokumen %d telah dihapus saat ekstraksi halaman %d. Ekstraksi dihentikan.", document_id, nomor)
                flush_cache()
                return Kemajuan(
                    document_id, STATUS_GAGAL, halaman_total,
                    len(sudah) + len(diproses), diproses,
                    time.perf_counter() - mulai,
                    pesan="Dokumen telah dihapus dari sistem.",
                )
            pesan = f"Halaman {nomor} gagal: {type(e).__name__}: {e}"
            logger.error(pesan)
            penyimpanan.catat_status(document_id, STATUS_GAGAL, pesan)
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai, pesan,
            )

        # 3. Disimpan SEBELUM apa pun yang lain. Kalau dokumen dihapus saat proses berjalan, simpan_halaman mengembalikan False
        tersimpan = penyimpanan.simpan_halaman(document_id, nomor, teks)
        if not tersimpan:
            logger.info("Dokumen %d telah dihapus sebelum menyimpan halaman %d. Menghentikan ekstraksi.", document_id, nomor)
            flush_cache()
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
                pesan="Dokumen telah dihapus dari sistem.",
            )

        penyimpanan.simpan_petunjuk(document_id, petunjuk)
        diproses.append(nomor)
        logger.info(
            "Dokumen %d: halaman %d tersimpan (%d/%d)",
            document_id, nomor, len(sudah) + len(diproses), halaman_total,
        )

        # Bersihkan timbunan prompt cache Ollama setiap 12 halaman agar RAM tidak bocor
        if len(diproses) % _FLUSH_CACHE_INTERVAL == 0:
            flush_cache()

        # Baru sesudah tersimpan, periksa permintaan jeda. Urutannya penting:
        # memeriksa lebih dulu berarti membuang halaman yang baru saja dibayar
        # dengan puluhan detik OCR.
        if penyimpanan.jeda_diminta(document_id):
            penyimpanan.catat_status(document_id, STATUS_JEDA)
            penyimpanan.batalkan_jeda(document_id)
            flush_cache()
            return Kemajuan(
                document_id, STATUS_JEDA, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
            )

    selesai = len(sudah) + len(diproses)
    checkpoint()
    status = STATUS_SELESAI if selesai >= halaman_total else STATUS_BERJALAN
    penyimpanan.catat_status(document_id, status)
    flush_cache()

    return Kemajuan(
        document_id, status, halaman_total, selesai, diproses,
        time.perf_counter() - mulai,
    )


