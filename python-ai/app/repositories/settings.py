"""Pengaturan tunggal dan konfigurasi RAG dengan konversi/fallback yang sama."""

import logging
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.repositories.connection import get_engine

logger = logging.getLogger("app.database")

def get_app_setting(key: str, default: Any = None) -> Any:
    """
    Mengambil satu nilai pengaturan dari tabel 'app_settings'.

    Args:
        key: Kunci setting (misal: 'rag_system_prompt')
        default: Nilai bawaan jika tidak ditemukan

    Returns:
        Nilai setting (string) atau default
    """
    engine = get_engine()
    query = text("SELECT setting_value FROM app_settings WHERE setting_key = :key LIMIT 1")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"key": key}).scalar()
            return result if result is not None else default
    except Exception as e:
        logger.warning("Gagal mengambil setting '%s' dari DB, gunakan default: %s", key, str(e))
        return default


def get_chatbot_rag_config() -> dict[str, Any]:
    """
    Mengambil seluruh konfigurasi Chatbot & RAG aktif dari basis data.
    """
    try:
        engine = get_engine()
        query = text(
            "SELECT setting_key, setting_value FROM app_settings "
            "WHERE setting_key IN ('llm_model_name', 'chatbot_name', 'chatbot_persona', 'rag_system_prompt', "
            "'rag_temperature', 'rag_top_k', 'rag_num_ctx', 'chatbot_greeting', 'chatbot_fallback_message', 'rag_citation_enabled')"
        )
        with engine.connect() as conn:
            rows = conn.execute(query).fetchall()
            settings_map = {row[0]: row[1] for row in rows}

        return {
            "llm_model_name": settings_map.get("llm_model_name") or settings.LLM_MODEL_NAME,
            "chatbot_name": settings_map.get("chatbot_name", "Asisten Virtual Diskominfotik"),
            "chatbot_persona": settings_map.get("chatbot_persona", "Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh"),
            "rag_system_prompt": settings_map.get("rag_system_prompt"),
            "rag_temperature": float(settings_map.get("rag_temperature", "0.2")),
            "rag_top_k": int(settings_map.get("rag_top_k", "8")),
            "rag_num_ctx": int(settings_map.get("rag_num_ctx", str(settings.LLM_NUM_CTX))),
            "chatbot_greeting": settings_map.get("chatbot_greeting", "Halo! Ada yang bisa saya bantu terkait SOP Diskominfotik?"),
            "chatbot_fallback_message": settings_map.get("chatbot_fallback_message", "Maaf, informasi tersebut tidak ditemukan di dalam dokumen SOP yang tersedia."),
            "rag_citation_enabled": settings_map.get("rag_citation_enabled", "true") == "true",
        }
    except Exception as e:
        logger.warning("Gagal mengambil rag_config dari DB, fallback default: %s", str(e))
        return {
            "llm_model_name": settings.LLM_MODEL_NAME,
            "chatbot_name": "Asisten Virtual Diskominfotik",
            "chatbot_persona": "Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh",
            "rag_system_prompt": None,
            "rag_temperature": 0.2,
            "rag_top_k": 8,
            "rag_num_ctx": settings.LLM_NUM_CTX,
            "chatbot_greeting": "Halo! Ada yang bisa saya bantu terkait SOP Diskominfotik?",
            "chatbot_fallback_message": "Maaf, informasi tersebut tidak ditemukan di dalam dokumen SOP yang tersedia.",
            "rag_citation_enabled": True,
        }


