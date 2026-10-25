"""Titik masuk kompatibel untuk PDF, OCR, prompt, dan pemeriksaan hasil.

Implementasi berada di app.services.ocr. Fungsi dan konstanta tetap tersedia
pada path ini untuk router, task, CLI, dan pembaca konfigurasi yang sudah ada.
Cache autodeteksi model hanya dimiliki ocr.vision.
"""

from app.services.ocr.pdf_io import (
    fitz,
    _MIN_TEXT_LENGTH,
    ZOOM_OCR,
    ZOOM_DIIZINKAN,
    _MUTU_JPEG,
    _resolve_pdf_path,
    render_halaman,
    ukuran_halaman,
    detect_pdf_type,
    _extract_text_from_page,
)
from app.services.ocr.prompts import (
    _PROMPT_OCR_DASAR,
    _PETUNJUK_TABEL_SOP,
    _PETUNJUK_KEPALA_SOP,
    _POLA_KATA_KUNCI,
    _sisipkan_kata_kunci,
)
from app.services.ocr.cleanup import (
    _strip_garbage,
    _POLA_PENANDA_HURUF,
    _MIN_RUNTUN_UNTUK_PERBAIKAN,
    perbaiki_penanda_daftar,
)
from app.services.ocr.vision import (
    _VISION_KEYWORDS,
    get_installed_vision_models,
    resolve_vision_model,
    vision_extract_general,
)
from app.services.ocr.sop import (
    _PENANDA_FORMULIR_SOP,
    _MIN_PENANDA_FORMULIR,
    _terlihat_formulir_sop,
    _OCR_ULANG_MAKS,
    _POLA_NIP,
    _kepala_sop_terlihat,
    _header_sop_tidak_lengkap,
    _bagian_kepala_hilang,
    _ocr_dengan_penjaga,
)
from app.services.ocr.pipeline import (
    _ekstrak_gambar_tersemat,
    _ekstrak_halaman,
    ekstrak_gambar_uji,
    ekstrak_satu_halaman,
    extract_text,
)
