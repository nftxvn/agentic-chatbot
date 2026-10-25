"""Route health publik dan diagnostik bertoken, beserta cache respons per proses.

Health memakai TTL 5 detik; diagnostik tetap memakai kondisi cache 3 detik
di handler. Konstanta diagnostik lama bernilai 10 tetap tersedia sebagai
ekspor kompatibilitas dan tidak menentukan kondisi cache yang berjalan.
"""

import os
import platform
import time

from fastapi import APIRouter, Depends, Response, status

from app.config import settings
from app.routers import documents
from app.services.diagnostics.health import _run_health_checks
from app.services.diagnostics.hardware import (
    _baca_nvidia_smi,
    _deteksi_os_platform,
    _baca_system_ram,
    _hitung_rekomendasi_hardware,
    _baca_ollama_ps,
    _hitung_kecocokan_model,
)

router = APIRouter()

_HEALTH_CACHE_TTL = 5


_health_cache: tuple[float, dict] | None = None


_MESIN_CACHE_TTL = 10


_mesin_cache: tuple[float, dict] | None = None


@router.get("/health", tags=["Health"])
@router.get("/api/health", tags=["Health"])
def health_check(response: Response) -> dict:
    """
    Health check yang benar-benar memeriksa dependensi: ChromaDB, MySQL, Redis,
    dan Ollama. Membalas 503 bila salah satu mati, sehingga pemantauan bisa
    membedakan "proses hidup" dari "layanan bisa melayani permintaan".

    Sengaja ditulis sinkron (`def`, bukan `async def`) supaya FastAPI
    menjalankannya di threadpool — seluruh pemeriksaan di dalamnya memblokir dan
    akan menahan event loop bila dijalankan langsung di atasnya.
    """
    global _health_cache

    now = time.monotonic()
    if _health_cache is not None and now - _health_cache[0] < _HEALTH_CACHE_TTL:
        payload = _health_cache[1]
    else:
        checks = _run_health_checks()
        payload = {
            "status": "healthy" if all(c["ok"] for c in checks.values()) else "degraded",
            "service": "ai-service",
            "model": settings.LLM_MODEL_NAME,
            "checks": checks,
        }
        _health_cache = (now, payload)

    if payload["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return payload


@router.get("/api/health/hardware", tags=["Health"])
def diagnostik_mesin(
    nocache: bool = False,
    model: str | None = None,
    _token: str = Depends(documents.verify_token),
) -> dict:
    """
    Konfigurasi efektif dan keadaan perangkat keras — hanya baca.
    Menyediakan data VRAM, RAM sistem, model aktif, dan rekomendasi jendela konteks (num_ctx).
    """
    from app.database import get_app_setting

    global _mesin_cache

    now = time.monotonic()
    if not nocache and _mesin_cache is not None and now - _mesin_cache[0] < 3.0:
        cached_payload = dict(_mesin_cache[1])
        if model:
            cached_payload["model_fit"] = _hitung_kecocokan_model(
                cached_payload.get("gpu"),
                cached_payload.get("ram"),
                model,
                cached_payload.get("konfigurasi", {}).get("num_ctx", 6144),
            )
        return cached_payload

    # Ambil nilai model & rag_num_ctx dari DB jika ada, fallback ke settings
    active_model = model or settings.LLM_MODEL_NAME
    active_ctx = settings.LLM_NUM_CTX
    try:
        if not model:
            model_val = get_app_setting("llm_model_name")
            if model_val:
                active_model = str(model_val).strip()
        ctx_val = get_app_setting("rag_num_ctx")
        if ctx_val is not None and str(ctx_val).isdigit():
            active_ctx = int(ctx_val)
    except Exception:
        pass

    gpu_data = _baca_nvidia_smi()
    ram_data = _baca_system_ram()
    ollama_data = _baca_ollama_ps()
    rekomendasi_data = _hitung_rekomendasi_hardware(gpu_data, ram_data, active_model)
    model_fit_data = _hitung_kecocokan_model(gpu_data, ram_data, active_model, active_ctx)

    is_wsl = "microsoft" in platform.release().lower() or "wsl" in platform.release().lower() or "WSL_DISTRO_NAME" in os.environ
    os_name = _deteksi_os_platform()
    env_label = "WSL2 (Windows Hyper-V vGPU D3D12)" if is_wsl else f"{os_name} (Native GPU Bare-Metal)"

    from app.services.pdf_processor import resolve_vision_model

    payload = {
        "konfigurasi": {
            "llm_model": active_model,
            "llm_model_default": settings.LLM_MODEL_NAME,
            "vision_model": resolve_vision_model(),
            "vision_model_default": settings.VISION_MODEL_NAME,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
            "embedding_device": settings.EMBEDDING_DEVICE,
            "num_ctx": active_ctx,
            "num_ctx_default": settings.LLM_NUM_CTX,
            # 0 berarti keputusan diserahkan ke auto-fit Ollama.
            "num_gpu": settings.LLM_NUM_GPU,
            "num_gpu_mode": "auto-fit" if settings.LLM_NUM_GPU == 0 else "dipaksa",
            "ollama_url": settings.OLLAMA_BASE_URL,
            "chroma_dir": str(settings.CHROMA_PERSIST_DIR),
            "flash_attention": os.environ.get("OLLAMA_FLASH_ATTENTION", "1"),
            "kv_cache_type": os.environ.get("OLLAMA_KV_CACHE_TYPE", "q8_0"),
        },
        "sistem": {
            "os_name": os_name,
            "python_version": platform.python_version(),
            "is_wsl": is_wsl,
            "environment_label": env_label,
        },
        "gpu": gpu_data,
        "ram": ram_data,
        "ollama": ollama_data,
        "rekomendasi": rekomendasi_data,
        "model_fit": model_fit_data,
    }
    _mesin_cache = (now, payload)
    return payload


