"""
Konfigurasi aplikasi AI Microservice.
Memuat semua environment variables menggunakan python-dotenv.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Muat file .env dari root project
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


# ── Mode luring HuggingFace ──────────────────────────────────────
# sentence_transformers memeriksa pembaruan model ke huggingface.co setiap kali
# dimuat, walau modelnya sudah lengkap di cache lokal. Bila jaringan lambat atau
# diblokir, pemeriksaan itu habis waktu lalu diulang lima kali dengan jeda
# menaik — satu sampai dua menit terbuang setiap skrip mulai.
#
# HF_HUB_OFFLINE menghentikan itu, TETAPI harus dinyalakan sendiri dan tidak
# pernah otomatis. Alasannya terbukti mahal: transformers memanggil
# is_base_mistral() -> model_info() yang menghubungi jaringan tanpa syarat, dan
# dalam mode luring panggilan itu MELEMPAR OfflineModeIsEnabled alih-alih
# dilewati — pemuatan model gagal total, bukan sekadar lambat. Menyalakannya
# otomatis berarti menukar keterlambatan yang menjengkelkan dengan kegagalan
# yang menghentikan pekerjaan.
#
# Bila kamu memang menyalakannya di .env, get_embedding_model() akan menangkap
# kegagalan itu dan mengulang sekali tanpa mode luring — lihat embedding_service.


def _lokasi_cache_hf() -> Path:
    """Folder cache HuggingFace, mengikuti urutan variabel env resminya."""
    for var in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        if os.getenv(var):
            return Path(os.getenv(var))
    if os.getenv("HF_HOME"):
        return Path(os.getenv("HF_HOME")) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


HF_LURING = os.getenv("HF_HUB_OFFLINE", "0") not in {"0", "false", "False", ""}

def _env_bool(name: str, default: str) -> bool:
    """Membaca variabel env bertipe boolean. Menerima 1/true/yes/on (tidak case-sensitive)."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    """Membaca variabel env berisi daftar yang dipisah koma, membuang entri kosong."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Settings:
    """
    Kelas konfigurasi utama.
    Semua nilai diambil dari environment variables dengan fallback default.
    """

    # --- LLM Configuration ---
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen2.5:7b")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    VISION_MODEL_NAME: str = os.getenv("VISION_MODEL_NAME", "qwen2.5vl")
    VISION_TIMEOUT: int = int(os.getenv("VISION_TIMEOUT", "300"))

    # --- Embedding ---
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Perangkat tempat model embedding dijalankan: "auto" | "cpu" | "cuda".
    #
    # DEFAULT "auto" berarti biarkan SentenceTransformer memilih — CUDA bila ada.
    # Itu pilihan yang benar di mesin dengan VRAM lega.
    #
    # Setel "cpu" HANYA di mesin yang VRAM-nya diperebutkan dengan LLM. bge-m3
    # memakan 2272 MiB VRAM (568 juta parameter, fp32), dan di kartu 6 GB itulah
    # yang menghalangi qwen3:8b masuk seluruhnya. Ongkos pindah ke CPU kecil:
    # yang di-embed hanya kalimat pertanyaan (~100 ms, dua kali per pertanyaan),
    # karena embedding dokumen sudah tersimpan di ChromaDB sejak ingest.
    # Jalur ingest Celery ikut ke CPU: ~69 ms/chunk, jauh di bawah OCR vision.
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "auto")

    # --- Reranker (Two-Stage RAG) ---
    # Model CrossEncoder untuk re-ranking kandidat chunk hasil hybrid retrieval.
    # Dijalankan di CPU (device='cpu') agar 100% VRAM GPU 6 GB tetap dialokasikan
    # penuh untuk LLM (qwen3:8b) tanpa OOM.
    RERANKER_MODEL_NAME: str = os.getenv(
        "RERANKER_MODEL_NAME", "BAAI/bge-reranker-base"
    )
    RERANKER_DEVICE: str = os.getenv("RERANKER_DEVICE", "cpu")
    RERANKER_ENABLED: bool = _env_bool("RERANKER_ENABLED", "true")
    RERANKER_TOP_CANDIDATES: int = int(os.getenv("RERANKER_TOP_CANDIDATES", "25"))
    # Ambang batas skor CrossEncoder (0.0 - 1.0). Potongan di bawah nilai ini disaring sebagai false-positive.
    RERANKER_MIN_SCORE: float = float(os.getenv("RERANKER_MIN_SCORE", "0.01"))

    # --- Vector DB (ChromaDB) ---
    _raw_chroma_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
    CHROMA_PERSIST_DIR: str = (
        str((Path(__file__).resolve().parent.parent / _raw_chroma_dir).resolve())
        if _raw_chroma_dir.startswith(".")
        else _raw_chroma_dir
    )

    # --- Database MySQL (Shared with Laravel) ---
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "agentic_copilot")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "secret")

    # --- Celery (Antrian tugas async) ---
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
    )

    # --- Security ---
    INTERNAL_API_TOKEN: str = os.getenv(
        "INTERNAL_API_TOKEN", "your-secure-internal-token-here"
    )

    # Autentikasi untuk POST /api/chat/stream.
    #
    # Default-nya AKTIF: tanpa penjaga, siapa pun yang bisa menjangkau port ini
    # dapat menanyai seluruh isi dokumen yang sudah di-ingest.
    #
    # Boleh dimatikan HANYA saat pengembangan lokal — React widget memanggil
    # endpoint ini langsung dari browser, sehingga menaruh INTERNAL_API_TOKEN di
    # sana berarti membocorkannya ke siapa pun yang membuka devtools (token yang
    # sama juga membuka /api/docs/*). Untuk produksi, biarkan aktif dan
    # teruskan permintaan lewat Laravel yang memegang token di sisi server.
    CHAT_STREAM_REQUIRE_AUTH: bool = _env_bool("CHAT_STREAM_REQUIRE_AUTH", "true")

    # Origin yang boleh memanggil API dari browser (dipisah koma).
    # Tidak boleh "*": dipasangkan dengan allow_credentials=True, Starlette
    # memantulkan balik origin peminta, sehingga situs mana pun bisa memanggil
    # API ini memakai kredensial pengunjungnya.
    CORS_ALLOW_ORIGINS: list[str] = _env_list(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
    )

    # Ukuran jendela konteks LLM (token) — DIPATOK ke satu nilai, tidak dihitung
    # per pertanyaan.
    #
    # Alasannya soal performa, bukan kualitas. Di Ollama, setiap nilai num_ctx
    # yang berbeda memaksa llama-server dimuat ulang dari nol (~23 detik di mesin
    # ini). num_ctx dinamis berarti tiap pertanyaan dengan panjang konteks
    # berbeda membayar reload itu — dan karena ekstraksi kata kunci memakai nilai
    # lain lagi, satu pertanyaan bisa memicu dua reload.
    #
    # 8192 cukup untuk konteks ~24.000 karakter (±10 potongan induk @ 1.500).
    # Pertanyaan daftar yang sangat panjang bisa terpotong — itu kompromi yang
    # disengaja; jalur enumerasi terprogram sudah menangani sebagian besar kasus
    # itu tanpa LLM.
    #
    # Naikkan HANYA setelah VRAM dibebaskan dan OLLAMA_KV_CACHE_TYPE=q8_0 aktif;
    # tanpa itu jendela lebih besar gagal alokasi ("failed to allocate buffer").
    LLM_NUM_CTX: int = int(os.getenv("LLM_NUM_CTX", "8192"))

    # Jumlah layer model yang dipaksa masuk GPU. 0 = serahkan ke auto-fit Ollama.
    #
    # DEFAULT-NYA SENGAJA 0 — aman di mesin mana pun. Nilai selain 0 hanya boleh
    # dipasang lewat .env, di mesin yang anggaran VRAM-nya SUDAH DIUKUR.
    # Memaksa layer melebihi kapasitas kartu tidak menghasilkan galat: VRAM
    # kelebihan muatan lalu melimpah diam-diam ke RAM host, dan throughput anjlok
    # (terukur 12,9 -> 5,5 tok/dtk di laptop pengembangan).
    #
    # Kapan perlu diisi: auto-fit llama.cpp selalu menyisakan 1024 MiB VRAM
    # sebagai cadangan. Di kartu besar cadangan itu tidak terasa; di kartu 6 GB
    # ia memakan 17% anggaran dan memaksa model dipecah ke CPU padahal sebenarnya
    # muat. Di situlah "99" (artinya "semua layer") menolong.
    #
    # PRASYARAT sebelum menaikkannya, keduanya wajib:
    #   1. EMBEDDING_DEVICE=cpu, supaya bge-m3 tidak ikut memakan VRAM
    #   2. Ollama dijalankan dengan OLLAMA_KV_CACHE_TYPE=q8_0
    #      (/etc/systemd/system/ollama.service.d/override.conf) — memangkas KV
    #      cache 8192 token dari 1152 MiB menjadi 612 MiB
    #
    # Prosedur pengukurannya ada di docs/ panduan deployment.
    LLM_NUM_GPU: int = int(os.getenv("LLM_NUM_GPU", "0"))

    # --- Debug ---
    # Menulis konteks retrieval terakhir ke debug_context.txt setiap ada
    # pertanyaan. Berguna saat menyetel retrieval, tapi JANGAN diaktifkan di
    # produksi: isinya potongan dokumen mentah dan file-nya ditimpa terus.
    DEBUG_DUMP_CONTEXT: bool = _env_bool("DEBUG_DUMP_CONTEXT", "false")

    @property
    def MYSQL_DATABASE_URL(self) -> str:
        """
        Menghasilkan URL koneksi SQLAlchemy untuk MySQL.
        Format: mysql+pymysql://user:password@host:port/database
        """
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )


# Instance singleton untuk digunakan di seluruh aplikasi
settings = Settings()
