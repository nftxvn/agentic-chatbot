"""Pembacaan hardware/Ollama dan estimasi kapasitas dengan aturan yang sama."""

import os
import platform

from app.config import settings
from app.services.diagnostics.health import _HEALTH_TIMEOUT

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


