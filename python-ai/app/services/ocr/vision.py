"""Pemilihan model vision, cache autodeteksi, dan request/retry OCR Ollama."""

import logging
import time

import requests

from app.config import settings
from app.services.ocr.cleanup import _strip_garbage
from app.services.ocr.prompts import _PROMPT_OCR_DASAR, _sisipkan_kata_kunci

logger = logging.getLogger("app.services.pdf_processor")

_VISION_KEYWORDS = (
    "vision",
    "vl",
    "llava",
    "minicpm",
    "bakllava",
    "moondream",
    "pixtral",
    "glm-4v",
    "deepseek-vl",
    "omnilmm",
    "cogvlm",
    "internvl",
)


_CACHED_AUTO_VISION_MODEL: tuple[str, float] | None = None


def get_installed_vision_models() -> list[str]:
    """
    Mengambil daftar nama model vision yang terpasang di server Ollama secara live.
    Mencari model yang namanya mengandung penanda model visual (vision, vl, llava, minicpm, dll).
    """
    try:
        r = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        if r.status_code != 200:
            return []
        data = r.json()
        models = data.get("models", [])
        found: list[str] = []
        for m in models:
            name = m.get("name", "")
            if not name:
                continue
            name_lower = name.lower()
            if any(kw in name_lower for kw in _VISION_KEYWORDS):
                found.append(name)
        return found
    except Exception as e:
        logger.debug("Gagal menghubungi Ollama untuk deteksi model vision: %s", e)
        return []


def resolve_vision_model(custom_model: str | None = None) -> str:
    """
    Menentukan model vision yang akan digunakan secara cerdas (Zero-Knowledge):

    1. Prioritas 1: Model eksplisit dari Kategori atau Payload (bila disetel pengguna via UI).
    2. Prioritas 2: Model vision global yang tersimpan di basis data `app_settings` (jika ada).
    3. Prioritas 3: Auto-detect cerdas ke Ollama (mencari model vision pertama yang aktif terpasang).
    4. Prioritas 4: Fallback aman ke `settings.VISION_MODEL_NAME` / 'qwen2.5vl'.
    """
    global _CACHED_AUTO_VISION_MODEL

    if custom_model and str(custom_model).strip():
        return str(custom_model).strip()

    # Cek apakah ada pengaturan global di app_settings (opsional)
    try:
        from app.database import get_app_setting

        global_vision = get_app_setting("vision_model_name") or get_app_setting("default_vision_model")
        if global_vision and str(global_vision).strip():
            return str(global_vision).strip()
    except Exception:
        pass

    # Cek cache deteksi otomatis (TTL 60 detik agar tidak spam Ollama di tiap halaman)
    now = time.time()
    if _CACHED_AUTO_VISION_MODEL and (now - _CACHED_AUTO_VISION_MODEL[1]) < 60:
        return _CACHED_AUTO_VISION_MODEL[0]

    # Auto-detect dari Ollama tags
    installed = get_installed_vision_models()
    if installed:
        detected = installed[0]
        _CACHED_AUTO_VISION_MODEL = (detected, now)
        logger.info("Auto-detect cerdas Vision Model dari Ollama: '%s'", detected)
        return detected

    # Fallback terakhir (jika Ollama offline atau belum ada model terpasang)
    fallback = (getattr(settings, "VISION_MODEL_NAME", None) or "qwen2.5vl").strip()
    return fallback


def vision_extract_general(
    img_base64: str,
    retries: int = 3,
    petunjuk: str | None = None,
    category_prompt: str | None = None,
    job_titles: str | None = None,
    vision_model: str | None = None,
    custom_prompts: dict | None = None,
) -> str:
    """
    Ekstraksi teks satu halaman gambar lewat model vision.

    Prompt disusun berlapis, dan urutannya disengaja:
        aturan dasar  ->  tambahan dari kategori  ->  petunjuk otomatis
    Prompt kategori MENAMBAH, tidak menggantikan. Aturan dasar memuat penjaga
    yang tidak boleh hilang (jangan menomori ulang, jangan menebak sel kosong),
    dan petunjuk otomatis memuat penjaga anti-karangan untuk halaman lanjutan
    formulir SOP yang tidak punya kepala.

    Args:
        img_base64: Halaman yang sudah dirender, dalam base64.
        retries: Percobaan ulang bila panggilan HTTP-nya gagal.
        petunjuk: Petunjuk format tambahan yang ditempelkan ke prompt dasar.
            Dibiarkan None untuk dokumen umum — itu jalur bawaannya.
        category_prompt: Panduan/instruksi khusus dari kategori dokumen di Laravel.
        job_titles: Daftar kata kunci/jabatan resmi dari kategori dokumen, sudah
            berbentuk teks dipisah koma.
        vision_model: Model vision spesifik kategori (opsional).
        custom_prompts: Kamus prompt kustom untuk menimpa aturan bawaan secara dinamis.
    """
    model_to_use = resolve_vision_model(vision_model)
    logger.info("Using general vision extraction pipeline with model: '%s'...", model_to_use)

    prompt_dasar = (custom_prompts.get("dasar") if custom_prompts else None) or _PROMPT_OCR_DASAR
    prompt = prompt_dasar
    if category_prompt:
        prompt += f"\n\n[PANDUAN KHUSUS KATEGORI DOKUMEN]:\n{category_prompt}\n"
    prompt = _sisipkan_kata_kunci(prompt, job_titles or "")
    if petunjuk:
        prompt += f"\n{petunjuk}"

    payload = {
        "model": model_to_use,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "options": {
            "num_ctx": 8192, 
            "num_predict": 2048, 
            "temperature": 0.1
        }
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=settings.VISION_TIMEOUT)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            if raw:
                return _strip_garbage(raw)
            else:
                logger.warning(f"Attempt {attempt}/{retries}: Model Vision OCR mengembalikan teks kosong")
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"Attempt {attempt}/{retries}: Timeout/Error saat vision extract: {e}")
            time.sleep(2)

    if last_error:
        raise RuntimeError(f"Gagal melakukan Vision OCR: {last_error}")
    raise RuntimeError("Model Vision OCR mengembalikan teks kosong")


