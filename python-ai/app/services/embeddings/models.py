"""Encoders embedding/reranker yang dimuat secara lazy dan fallback Ollama."""

import logging
import os
import sys

# Muat .env sebelum sentence_transformers/huggingface_hub membaca mode luring.
from app.config import settings

from sentence_transformers import CrossEncoder, SentenceTransformer

logger = logging.getLogger("app.services.embedding_service")

_embedding_model: SentenceTransformer | None = None
_reranker_model: CrossEncoder | None = None

# Perangkat tempat bge-m3 dijalankan. Lihat EMBEDDING_DEVICE di config.py untuk
# alasan dan kapan perlu diubah.
#
# None diserahkan ke SentenceTransformer, yang berarti auto-detect (CUDA bila
# tersedia) — perilaku bawaan pustakanya.
_EMBEDDING_DEVICE = (
    None if settings.EMBEDDING_DEVICE.strip().lower() == "auto"
    else settings.EMBEDDING_DEVICE.strip().lower()
)


def get_embedding_model(local_only: bool = True) -> SentenceTransformer | None:
    """
    Mendapatkan model SentenceTransformer (lazy loading).
    
    Args:
        local_only: Bila True, hanya mencoba memuat dari disk cache lokal tanpa mengunduh dari internet.
                    Bila model belum terunduh, langsung return None agar bisa dialihkan ke Ollama.
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    # 1. Coba muat dari cache lokal terlebih dahulu (cepat, tanpa blocking download)
    try:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=_EMBEDDING_DEVICE,
            local_files_only=True,
        )
        logger.info(
            "Model embedding SentenceTransformer berhasil dimuat dari disk cache lokal: %s (%s)",
            settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DEVICE,
        )
        return _embedding_model
    except Exception:
        pass

    if local_only:
        return None

    # 2. Jika local_only=False (Ollama tidak tersedia), baru lakukan unduhan online
    logger.info(
        "Memuat/mengunduh model embedding online: %s di %s ...",
        settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_DEVICE,
    )
    try:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=_EMBEDDING_DEVICE,
            local_files_only=False,
        )
        logger.info("Model embedding SentenceTransformer berhasil diunduh dan dimuat")
        return _embedding_model
    except Exception as e:                                      # noqa: BLE001
        if type(e).__name__ == "OfflineModeIsEnabled":
            os.environ.pop("HF_HUB_OFFLINE", None)
            konstanta = sys.modules.get("huggingface_hub.constants")
            if konstanta is not None:
                konstanta.HF_HUB_OFFLINE = False
            try:
                _embedding_model = SentenceTransformer(
                    settings.EMBEDDING_MODEL_NAME,
                    device=_EMBEDDING_DEVICE,
                    local_files_only=False,
                )
                return _embedding_model
            except Exception as retry_err:
                logger.warning("Gagal memuat SentenceTransformer setelah reset luring: %s", retry_err)
                return None
        logger.warning("Gagal mengunduh model SentenceTransformer (%s): %s", settings.EMBEDDING_MODEL_NAME, e)
        return None


def _get_available_ollama_models() -> list[str]:
    """Cek daftar model yang terpasang di Ollama secara dinamis."""
    import requests
    try:
        res = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            return [m.get("name", "") for m in models_data if m.get("name")]
    except Exception:
        pass
    return []


def _encode_via_ollama(texts: list[str]) -> list[list[float]]:
    """
    Fallback embedding menggunakan Ollama API di host bila model lokal belum terunduh.
    Mencari model embedding bge-m3, nomic-embed-text, atau LLM aktif dari Ollama tags.
    Menggunakan batching agar efisien dan tidak timeout.
    """
    import requests

    if not texts:
        return []

    installed = _get_available_ollama_models()
    
    # Prioritaskan model khusus embedding yang terpasang di Ollama
    candidate_order = ["bge-m3", "bge", "nomic-embed-text", "all-minilm", settings.LLM_MODEL_NAME, "qwen2.5:7b", "qwen3:8b"]
    
    selected_models: list[str] = []
    for cand in candidate_order:
        for inst in installed:
            if cand in inst.lower() and inst not in selected_models:
                selected_models.append(inst)
    
    for cand in candidate_order:
        if cand not in selected_models:
            selected_models.append(cand)

    batch_size = 25
    for m_name in selected_models:
        all_embeddings = []
        success = True
        
        # 1. Coba endpoint batch /api/embed (Ollama v0.1.34+)
        try:
            for i in range(0, len(texts), batch_size):
                chunk = texts[i : i + batch_size]
                res = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embed",
                    json={"model": m_name, "input": chunk},
                    timeout=60,
                )
                if res.status_code == 200:
                    data = res.json()
                    embs = data.get("embeddings", [])
                    if embs and len(embs) == len(chunk):
                        all_embeddings.extend(embs)
                    else:
                        success = False
                        break
                else:
                    success = False
                    break
                    
            if success and len(all_embeddings) == len(texts):
                logger.info("Berhasil membuat %d embeddings via Ollama /api/embed (model: %s)", len(texts), m_name)
                return all_embeddings
        except Exception:
            pass

        # 2. Coba endpoint single /api/embeddings jika /api/embed tidak merespon
        try:
            all_embeddings = []
            for t in texts:
                res = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": m_name, "prompt": t},
                    timeout=30,
                )
                if res.status_code == 200:
                    emb = res.json().get("embedding", [])
                    if emb:
                        all_embeddings.append(emb)
                    else:
                        break
                else:
                    break
            if len(all_embeddings) == len(texts):
                logger.info("Berhasil membuat %d embeddings via Ollama /api/embeddings (model: %s)", len(texts), m_name)
                return all_embeddings
        except Exception:
            continue

    raise RuntimeError("Ollama embedding tidak merespon atau model tidak cocok.")


def encode_texts(texts: list[str]) -> list[list[float]]:
    """
    Menghasilkan embedding vektor dari daftar teks.
    Prioritas:
      1. Ollama Embedding di host (GPU-accelerated di host, ultra-cepat 0.05s).
      2. Model SentenceTransformer dari cache lokal disk.
      3. Unduh model SentenceTransformer online (fallback terakhir).
    """
    if not texts:
        return []

    # 1. Prioritas Utama: Coba via Ollama di host (GPU-accelerated)
    try:
        return _encode_via_ollama(texts)
    except Exception:
        pass

    # 2. Coba dari cache lokal disk
    model = get_embedding_model(local_only=True)
    if model is not None:
        try:
            return model.encode(texts, show_progress_bar=False).tolist()
        except Exception as e:
            logger.warning("Eksekusi SentenceTransformer lokal gagal (%s).", e)

    # 3. Fallback: Unduh SentenceTransformer online
    model_online = get_embedding_model(local_only=False)
    if model_online is not None:
        return model_online.encode(texts, show_progress_bar=False).tolist()

    raise RuntimeError("Gagal menghasilkan embedding: Ollama tidak merespon, cache lokal tidak ada, dan unduhan online gagal.")


def encode_query(query: str) -> list[float]:
    """
    Menghasilkan 1D embedding vektor untuk satu kalimat query pencarian.
    """
    embs = encode_texts([query])
    if embs:
        return embs[0]
    return []


def get_reranker_model() -> CrossEncoder | None:
    """
    Mendapatkan model CrossEncoder Reranker (lazy loading).
    Model hanya dimuat sekali saat pertama kali dipanggil.
    Dijalankan di CPU (device='cpu') agar 100% VRAM GPU tetap dialokasikan
    penuh untuk LLM tanpa OOM.

    Bila model belum terunduh atau gagal dimuat, fungsi ini aman mengembalikan None
    dan sistem RAG secara otomatis beralih ke ranking RRF (Reciprocal Rank Fusion)
    standar tanpa galat dan tanpa jeda.
    """
    global _reranker_model
    if not settings.RERANKER_ENABLED:
        return None
    if _reranker_model is not None:
        return _reranker_model

    # 1. Coba muat dari cache lokal terlebih dahulu (cepat, tanpa hanging)
    try:
        _reranker_model = CrossEncoder(
            settings.RERANKER_MODEL_NAME,
            device=settings.RERANKER_DEVICE,
            local_files_only=True,
        )
        logger.info("Model Reranker berhasil dimuat dari disk cache: %s", settings.RERANKER_MODEL_NAME)
        return _reranker_model
    except Exception:
        pass

    # 2. Coba unduh/muat online dengan penanganan galat aman
    logger.info(
        "Memuat model Reranker: %s di %s ...",
        settings.RERANKER_MODEL_NAME, settings.RERANKER_DEVICE,
    )
    try:
        _reranker_model = CrossEncoder(
            settings.RERANKER_MODEL_NAME,
            device=settings.RERANKER_DEVICE,
            local_files_only=False,
        )
        logger.info("Model Reranker berhasil dimuat di %s", settings.RERANKER_DEVICE)
        return _reranker_model
    except Exception as e:                                      # noqa: BLE001
        logger.warning(
            "Model Reranker (%s) tidak tersedia (%s). RAG berjalan optimal dengan RRF standar.",
            settings.RERANKER_MODEL_NAME, e,
        )
        _reranker_model = None

    return _reranker_model
