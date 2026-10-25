"""Document prompts workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("app.routers.documents")


def get_ollama_tags() -> dict:
    """Mengambil daftar model yang terpasang di server Ollama."""
    import requests

    try:
        r = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return r.json()
        return {"models": []}
    except Exception as e:
        logger.warning("Gagal mengambil tag Ollama: %s", e)
        return {"models": []}


def prompt_ekstraksi_bawaan() -> dict:
    """
    Teks prompt bawaan yang BENAR-BENAR dipakai saat ekstraksi.

    Diambil langsung dari konstanta di pdf_processor, bukan disalin ke frontend.
    Salinan di frontend pernah ada dan itulah sumber masalahnya: teksnya mirip
    tapi tidak sama, admin menyetel berdasarkan teks yang tidak pernah berjalan,
    dan tidak ada yang memberi tahu ketika keduanya melenceng. Dengan diambil
    dari sini, keduanya tidak bisa berbeda.
    """
    from app.services import pdf_processor as pp

    return {
        "dasar": {
            "judul": "Aturan dasar",
            "kapan": "",
            "teks": pp._PROMPT_OCR_DASAR,
        },
        "tabel_sop": {
            "judul": "Petunjuk tabel prosedur SOP",
            "kapan": (
                "Dipasang otomatis begitu sebuah halaman terdeteksi berformat "
                "formulir SOP, lalu ikut dipakai pada halaman-halaman berikutnya."
            ),
            "teks": pp._PETUNJUK_TABEL_SOP,
        },
        "kepala_sop": {
            "judul": "Petunjuk kepala formulir SOP",
            "kapan": (
                "Hanya dipasang pada halaman yang kepala formulirnya memang "
                "terlihat ('Nomor SOP', 'Nama SOP', 'Disahkan Oleh')."
            ),
            "teks": pp._PETUNJUK_KEPALA_SOP,
        },
    }


def test_prompt_endpoint(payload: dict) -> dict:
    """
    Uji coba prompt ekstraksi pada satu gambar.

    Menjalankan gambar lewat `ekstrak_gambar_uji`, yaitu jalur vision yang SAMA
    dengan yang dipakai tombol Ekstraksi. Endpoint ini sengaja tidak punya
    logika prompt sendiri — dulu punya, dan itulah sumber kebingungannya:
    sandbox memakai prompt kategori sebagai pengganti aturan dasar dan tidak
    mengenal deteksi formulir SOP, sehingga hasil uji tidak mewakili hasil
    sungguhan.

    Tahap koreksi LLM juga sudah dihapus. Pipeline produksi tidak punya tahap
    itu — koreksi dikerjakan manusia lewat editor koreksi — dan menyimulasikan
    tahap yang tidak ada membuat hasil uji makin jauh dari kenyataan. Di mesin
    ber-VRAM terbatas tahap itu juga memaksa tukar model vision <-> teks pada
    tiap halaman, yang mahal.
    """
    import time

    from app.services.pdf_processor import ekstrak_gambar_uji

    start_time = time.time()
    try:
        image_base64 = payload.get("image_base64", "")
        if not image_base64:
            return {"success": False, "error": "Gambar (base64) wajib diunggah."}

        # Bersihkan format data URL bila ada
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]

        category = payload.get("category") or {}
        vision_model = (category.get("vision_model") or "").strip() or None

        # Kata kunci disimpan sebagai daftar di prompt_variables; sisi ekstraksi
        # menerimanya sebagai teks. Kunci lama `job_titles` tetap dibaca supaya
        # kategori yang sudah ada tidak kehilangan datanya.
        prompt_vars = category.get("prompt_variables") or {}
        daftar = prompt_vars.get("kata_kunci") or prompt_vars.get("job_titles") or []
        kata_kunci = ", ".join(daftar) if isinstance(daftar, list) else str(daftar)
        custom_prompts = prompt_vars.get("custom_prompts") or category.get("custom_prompts") or None

        hasil = ekstrak_gambar_uji(
            image_base64,
            category_prompt=(category.get("vision_prompt") or "").strip() or None,
            job_titles=kata_kunci or None,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

        return {
            "success": True,
            "result": hasil["teks"],
            "raw_ocr": hasil["teks_awal"],
            "petunjuk_aktif": hasil["petunjuk_aktif"],
            "duration": round(time.time() - start_time, 2),
        }
    except Exception as e:
        logger.exception("Error saat uji coba prompt")
        return {
            "success": False,
            "error": str(e),
            "duration": round(time.time() - start_time, 2),
        }

