"""
Aplikasi utama FastAPI untuk Agentic IT Support Copilot - AI Service.
Menyediakan endpoint untuk pemrosesan dokumen dan RAG-based chat.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, documents, ekstraksi

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Redam kegagalan telemetri ChromaDB. Dependensinya tidak sepadan: chromadb
# 0.5.5 memanggil posthog.capture() dengan 3 argumen posisional, sedangkan
# posthog 7.x hanya menerima 1. Akibatnya SETIAP operasi ChromaDB — termasuk
# tiap pertanyaan pengguna — menuliskan "Failed to send telemetry event ...:
# capture() takes 1 positional argument but 3 were given" ke log server.
#
# Tidak ada dampak fungsional: yang gagal hanya pengiriman statistik anonim,
# dan pengirimannya memang sudah dimatikan lewat Settings di
# embedding_service. Yang tersisa murni kebisingan log.
#
# CRITICAL, bukan ERROR: pesan ini dicatat dengan logger.error(), dan ambang
# menyaring level di BAWAHnya — menyetel ERROR justru meloloskannya.
for _telemetry_logger in ("chromadb.telemetry", "posthog", "backoff"):
    logging.getLogger(_telemetry_logger).setLevel(logging.CRITICAL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan event handler untuk startup dan shutdown.
    Mencatat informasi konfigurasi saat aplikasi dimulai.
    """
    # --- Startup ---
    logger.info("=" * 60)
    logger.info("🚀 Memulai Agentic IT Support Copilot - AI Service")
    logger.info("=" * 60)
    logger.info("📦 Model LLM       : %s", settings.LLM_MODEL_NAME)
    logger.info("🌐 Ollama URL      : %s", settings.OLLAMA_BASE_URL)
    logger.info("🔤 Embedding Model : %s", settings.EMBEDDING_MODEL_NAME)
    logger.info("💾 ChromaDB Dir    : %s", settings.CHROMA_PERSIST_DIR)
    logger.info("🗄️  MySQL Database  : %s@%s:%d/%s",
                settings.MYSQL_USER, settings.MYSQL_HOST,
                settings.MYSQL_PORT, settings.MYSQL_DATABASE)
    logger.info("📮 Celery Broker   : %s", settings.CELERY_BROKER_URL)
    logger.info("=" * 60)

    yield  # Aplikasi berjalan di sini

    # --- Shutdown ---
    logger.info("🛑 Menghentikan AI Service...")
    logger.info("Cleanup selesai. Sampai jumpa! 👋")


# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="Agentic IT Support Copilot - AI Service",
    description="Microservice AI untuk memproses dokumen dan menyediakan RAG-based chat",
    version="1.0.0",
    lifespan=lifespan,
)

# Konfigurasi CORS.
#
# Origin dibaca dari CORS_ALLOW_ORIGINS di .env, bukan "*". Kombinasi
# allow_origins=["*"] dengan allow_credentials=True membuat Starlette
# memantulkan balik origin peminta apa pun, sehingga penjagaan CORS-nya praktis
# tidak ada — situs mana pun bisa memanggil API ini memakai kredensial
# pengunjungnya.
#
# Method dan header juga dipersempit ke yang benar-benar dipakai.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Daftarkan routers
app.include_router(documents.router)
app.include_router(ekstraksi.router)
app.include_router(chat.router)


# ── Health check ────────────────────────────────────────────────

# Batas waktu tiap pemeriksaan. Sengaja pendek: health check yang ikut
# menggantung saat dependensinya menggantung tidak memberi tahu apa pun.
_HEALTH_TIMEOUT = 3

# Hasil pemeriksaan disimpan sebentar. /health tidak butuh autentikasi, dan tanpa
# cache setiap permintaan membuka koneksi MySQL + Redis + satu request HTTP ke
# Ollama — artinya endpoint ini bisa dipakai untuk membebani dependensinya.
# Pemantauan umumnya menyapa tiap 10–30 detik, jadi 5 detik tidak mengurangi
# kegunaannya.
_HEALTH_CACHE_TTL = 5
_health_cache: tuple[float, dict] | None = None


def _check_chromadb() -> dict:
    """Basis data vektor bisa dibuka dan jumlah vektornya terbaca."""
    from app.services.embedding_service import get_chroma_collection

    return {"ok": True, "detail": f"{get_chroma_collection().count()} vektor"}


def _check_mysql() -> dict:
    """Koneksi ke MySQL yang dipakai bersama Laravel masih hidup."""
    from sqlalchemy import text

    from app.database import get_engine

    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True, "detail": settings.MYSQL_DATABASE}


def _check_redis() -> dict:
    """Broker Celery menjawab PING — tanpa ini dokumen tidak bisa masuk antrean."""
    import redis

    client = redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=_HEALTH_TIMEOUT,
        socket_timeout=_HEALTH_TIMEOUT,
    )
    try:
        client.ping()
    finally:
        client.close()
    return {"ok": True, "detail": "PING"}


def _check_ollama() -> dict:
    """Ollama hidup DAN model chat yang dikonfigurasi benar-benar sudah di-pull."""
    import requests

    response = requests.get(
        f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=_HEALTH_TIMEOUT
    )
    response.raise_for_status()

    # Ollama menuliskan tag lengkap ("qwen2.5:7b"); nama tanpa tag dianggap ":latest".
    installed = {model.get("name", "") for model in response.json().get("models", [])}
    wanted = settings.LLM_MODEL_NAME
    if wanted not in installed and f"{wanted}:latest" not in installed:
        return {"ok": False, "detail": f"model '{wanted}' belum di-pull"}

    return {"ok": True, "detail": wanted}


_HEALTH_CHECKS = {
    "chromadb": _check_chromadb,
    "mysql": _check_mysql,
    "redis": _check_redis,
    "ollama": _check_ollama,
}


def _run_health_checks() -> dict:
    """Jalankan seluruh pemeriksaan; kegagalan satu dependensi tidak menghentikan sisanya."""
    results: dict[str, dict] = {}

    for name, check in _HEALTH_CHECKS.items():
        try:
            results[name] = check()
        except Exception as e:
            # Hanya nama kelas exception yang dilaporkan. Endpoint ini terbuka
            # tanpa autentikasi, dan pesan exception mentah bisa memuat host,
            # nama pengguna basis data, atau potongan kredensial.
            logger.warning("Health check '%s' gagal: %s", name, e)
            results[name] = {"ok": False, "detail": type(e).__name__}

    return results


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
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


# ── Diagnostik mesin ────────────────────────────────────────────
#
# Sengaja DIPISAH dari /health dan DIBERI PENJAGA TOKEN. /health terbuka tanpa
# autentikasi supaya pemantauan bisa menyapanya; blok di bawah ini memuat nama
# model, kapasitas VRAM, dan nilai konfigurasi efektif — keterangan infrastruktur
# yang tidak perlu diketahui publik.
#
# Gunanya untuk serah terima: admin server dapat melihat model termuat penuh di
# GPU atau tidak tanpa perlu SSH dan membaca journalctl.

_MESIN_CACHE_TTL = 10
_mesin_cache: tuple[float, dict] | None = None


def _baca_nvidia_smi() -> dict | None:
    """
    Kapasitas dan pemakaian VRAM. Mengembalikan None bila mesinnya tidak punya
    GPU NVIDIA — itu keadaan yang sah, bukan galat, jadi jangan dijadikan error.
    """
    import subprocess

    try:
        keluaran = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=_HEALTH_TIMEOUT,
        )
        if keluaran.returncode != 0 or not keluaran.stdout.strip():
            return None
        nama, total, dipakai, bebas, util = [
            b.strip() for b in keluaran.stdout.strip().split("\n")[0].split(",")
        ]
        return {
            "nama": nama,
            "vram_total_mib": int(total),
            "vram_dipakai_mib": int(dipakai),
            "vram_bebas_mib": int(bebas),
            "utilisasi_persen": int(util),
        }
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None


import os
import platform

def _deteksi_os_platform() -> str:
    """Deteksi nama OS dan distro Linux secara dinamis."""
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        return f"{platform.system()} {platform.release()}"
    except Exception:
        return platform.system() or "Linux Server"


def _baca_system_ram() -> dict | None:
    """
    Membaca kapasitas dan penggunaan RAM sistem dari /proc/meminfo atau psutil.
    """
    try:
        if os.path.exists("/proc/meminfo"):
            meminfo: dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        if val.isdigit():
                            meminfo[key] = int(val)
            total_kb = meminfo.get("MemTotal", 0)
            avail_kb = meminfo.get("MemAvailable", 0)
            used_kb = max(0, total_kb - avail_kb)
            return {
                "ram_total_mib": round(total_kb / 1024),
                "ram_dipakai_mib": round(used_kb / 1024),
                "ram_bebas_mib": round(avail_kb / 1024),
            }
        else:
            import psutil
            vm = psutil.virtual_memory()
            return {
                "ram_total_mib": round(vm.total / 1048576),
                "ram_dipakai_mib": round(vm.used / 1048576),
                "ram_bebas_mib": round(vm.available / 1048576),
            }
    except Exception:
        return None


def _hitung_rekomendasi_hardware(
    gpu_info: dict | None,
    ram_info: dict | None,
    model_name: str,
) -> dict:
    """
    Menghitung rekomendasi ukuran jendela konteks (num_ctx) berdasarkan
    spesifikasi GPU VRAM dan RAM sistem yang terdeteksi secara real-time.
    """
    model_lower = model_name.lower()
    # Taksiran bobot model (MiB) untuk kuantisasi 4-bit standar
    if "70b" in model_lower:
        model_size_mib = 40000
    elif "14b" in model_lower or "13b" in model_lower:
        model_size_mib = 9000
    elif "8b" in model_lower or "7b" in model_lower:
        model_size_mib = 4650
    elif "3b" in model_lower or "4b" in model_lower:
        model_size_mib = 2200
    elif "1.5b" in model_lower or "0.5b" in model_lower:
        model_size_mib = 1000
    else:
        model_size_mib = 4650

    has_gpu = gpu_info is not None and gpu_info.get("vram_total_mib", 0) > 0
    vram_total = gpu_info.get("vram_total_mib", 0) if has_gpu else 0
    gpu_name = gpu_info.get("nama", "GPU NVIDIA") if has_gpu else "CPU"

    ram_total_gb = round((ram_info.get("ram_total_mib", 0) if ram_info else 0) / 1024, 1)

    if has_gpu:
        vram_total_gb = round(vram_total / 1024, 1)
        ringkasan = f"{gpu_name} ({vram_total_gb} GB VRAM) | RAM Sistem: {ram_total_gb} GB"

        if vram_total >= 22000:
            rec_ctx = 32768
            penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) sangat leluasa. Mendukung jendela konteks maksimal 32.768 token untuk dokumen super panjang."
        elif vram_total >= 14000:
            rec_ctx = 16384
            penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) memiliki kapasitas besar. Rekomendasi 16.384 token untuk retrieval multi-dokumen."
        elif vram_total >= 10000:
            rec_ctx = 12288 if ("8b" in model_lower or "7b" in model_lower) else 16384
            penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) mampu menampung {rec_ctx} token dengan 100% layer di GPU."
        elif vram_total >= 7500:
            rec_ctx = 8192
            penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) ideal untuk konteks 8.192 token pada model {model_name}."
        elif vram_total >= 5400:
            if "8b" in model_lower or "7b" in model_lower:
                rec_ctx = 6144
                penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) terdeteksi. Untuk model {model_name}, kapasitas 6.144 token adalah sweet spot optimal agar seluruh layer & KV Cache termuat 100% di VRAM tanpa offload ke CPU."
            else:
                rec_ctx = 16384
                penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) dengan model ringan {model_name} dapat menggunakan hingga 16.384 token."
        elif vram_total >= 3500:
            rec_ctx = 4096 if ("8b" in model_lower or "7b" in model_lower) else 8192
            penjelasan = f"GPU {gpu_name} ({vram_total_gb} GB VRAM) direkomendasikan menggunakan {rec_ctx} token agar tidak melebihi batas VRAM."
        else:
            rec_ctx = 2048
            penjelasan = f"GPU VRAM terbatas ({vram_total_gb} GB). Disarankan menggunakan 2.048 token."
    else:
        ringkasan = f"CPU Mode (Tanpa GPU NVIDIA) | RAM Sistem: {ram_total_gb} GB"
        if ram_total_gb >= 16:
            rec_ctx = 8192
            penjelasan = "Berjalan di CPU dengan RAM sistem lega. Rekomendasi 8.192 token."
        elif ram_total_gb >= 8:
            rec_ctx = 4096
            penjelasan = "Berjalan di CPU dengan RAM sistem standar. Rekomendasi 4.096 token untuk menjaga kecepatan inferensi."
        else:
            rec_ctx = 2048
            penjelasan = "RAM sistem terbatas. Rekomendasi 2.048 token untuk mencegah out-of-memory."

    return {
        "recommended_num_ctx": rec_ctx,
        "preset_options": [2048, 4096, 6144, 8192, 12288, 16384],
        "ringkasan_hardware": ringkasan,
        "penjelasan": penjelasan,
        "model_name": model_name,
        "model_size_mib": model_size_mib,
    }


def _baca_ollama_ps() -> dict | None:
    """
    Model yang sedang termuat beserta pembagian CPU/GPU-nya. Ollama melaporkan
    size dan size_vram; selisihnya adalah bagian yang jatuh ke CPU.
    """
    import requests

    try:
        r = requests.get(f"{settings.OLLAMA_BASE_URL}/api/ps", timeout=_HEALTH_TIMEOUT)
        r.raise_for_status()
        model = (r.json().get("models") or [None])[0]
        if not model:
            return {"termuat": False}

        total = model.get("size", 0)
        di_vram = model.get("size_vram", 0)
        return {
            "termuat": True,
            "nama": model.get("name"),
            "ukuran_mib": round(total / 1048576),
            "di_gpu_mib": round(di_vram / 1048576),
            "persen_di_gpu": round(di_vram / total * 100) if total else 0,
            "konteks": (model.get("context_length")
                        or model.get("details", {}).get("context_length")),
        }
    except Exception:
        return None


def _hitung_kecocokan_model(
    gpu_info: dict | None,
    ram_info: dict | None,
    model_name: str,
    ctx_tokens: int = 6144,
) -> dict:
    """
    Menghitung kecocokan kapasitas VRAM/RAM real-time untuk model tertentu.
    """
    model_lower = model_name.lower()
    if "70b" in model_lower:
        model_weight_mib = 40000
    elif "32b" in model_lower:
        model_weight_mib = 20000
    elif "14b" in model_lower or "13b" in model_lower:
        model_weight_mib = 9200
    elif "8b" in model_lower or "7b" in model_lower:
        model_weight_mib = 4800
    elif "3b" in model_lower or "4b" in model_lower:
        model_weight_mib = 2100
    elif "1.5b" in model_lower or "0.5b" in model_lower or "1b" in model_lower:
        model_weight_mib = 1100
    else:
        model_weight_mib = 4800

    # Estimasi KV Cache per 1000 token (~100-150 MiB untuk FP16 / Q8 KV cache)
    kv_cache_mib = round((ctx_tokens / 1024) * 120)
    total_required_mib = model_weight_mib + kv_cache_mib
    total_required_gb = round(total_required_mib / 1024, 1)

    has_gpu = gpu_info is not None and gpu_info.get("vram_total_mib", 0) > 0

    if has_gpu:
        vram_total_mib = gpu_info.get("vram_total_mib", 0)
        vram_free_mib = gpu_info.get("vram_bebas_mib", 0)
        vram_used_mib = gpu_info.get("vram_dipakai_mib", 0)
        vram_free_gb = round(vram_free_mib / 1024, 1)
        vram_total_gb = round(vram_total_mib / 1024, 1)

        if vram_free_mib >= total_required_mib:
            fit_status = "optimal"
            fit_badge = "100% GPU Offload (Optimal)"
            fit_message = f"Sisa VRAM bebas ({vram_free_gb} GB) mencukupi kebutuhan model ({total_required_gb} GB). Seluruh layer termuat penuh di GPU dengan kecepatan maksimal."
        elif vram_total_mib >= total_required_mib:
            fit_status = "shared_warning"
            fit_badge = "VRAM Terbagi Proses Lain"
            fit_message = f"Total VRAM GPU ({vram_total_gb} GB) mencukupi, namun sisa VRAM bebas saat ini hanya {vram_free_gb} GB karena terpakai oleh aplikasi/model lain. Tutup proses lain agar model dapat termuat 100% di GPU."
        else:
            fit_status = "exceeds_gpu"
            fit_badge = "Melebihi Kapasitas GPU (Partial Offload)"
            fit_message = f"Kebutuhan model ({total_required_gb} GB) melebihi kapasitas total VRAM GPU ({vram_total_gb} GB). Sebagian layer model akan dialihkan ke RAM sistem, kecepatan inferensi akan menurun."
    else:
        ram_free_mib = ram_info.get("ram_bebas_mib", 0) if ram_info else 0
        ram_free_gb = round(ram_free_mib / 1024, 1)
        fit_status = "cpu_only"
        fit_badge = "Mode CPU (RAM Sistem)"
        fit_message = f"Berjalan di CPU tanpa GPU NVIDIA. Membutuhkan alokasi ~{total_required_gb} GB dari RAM sistem (Sisa RAM bebas: {ram_free_gb} GB)."

    return {
        "model_name": model_name,
        "model_weight_mib": model_weight_mib,
        "kv_cache_mib": kv_cache_mib,
        "total_required_mib": total_required_mib,
        "total_required_gb": total_required_gb,
        "fit_status": fit_status,
        "fit_badge": fit_badge,
        "fit_message": fit_message,
    }


@app.get("/api/health/mesin", tags=["Health"])
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

    payload = {
        "konfigurasi": {
            "llm_model": active_model,
            "llm_model_default": settings.LLM_MODEL_NAME,
            "vision_model": settings.VISION_MODEL_NAME,
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

