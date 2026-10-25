"""Direktori dan FAQ aktif dengan cache wall-clock 5 detik serta fallback stale."""

import logging
import time
from typing import Any

from sqlalchemy import text

from app.repositories.connection import get_engine

logger = logging.getLogger("app.database")

_fast_paths_cache: tuple[float, list[dict[str, Any]]] | None = None


_directories_cache: tuple[float, list[dict[str, Any]]] | None = None


_CACHE_TTL_SECONDS = 5.0


def get_active_fast_paths() -> list[dict[str, Any]]:
    """
    Mengambil seluruh data Fast-Path FAQ yang aktif dari tabel 'chatbot_fast_paths'.
    Menggunakan cache in-memory 5 detik untuk performa tinggi (<0.01ms).
    """
    global _fast_paths_cache
    now = time.time()
    if _fast_paths_cache is not None and (now - _fast_paths_cache[0]) < _CACHE_TTL_SECONDS:
        return _fast_paths_cache[1]

    try:
        engine = get_engine()
        query = text(
            "SELECT id, category, title, keywords, response_text, sort_order "
            "FROM chatbot_fast_paths WHERE is_active = 1 "
            "ORDER BY sort_order ASC, id DESC"
        )
        with engine.connect() as conn:
            rows = conn.execute(query).fetchall()
            items = [
                {
                    "id": row[0],
                    "category": row[1],
                    "title": row[2],
                    "keywords": [k.strip().lower() for k in (row[3] or "").split(",") if k.strip()],
                    "response_text": row[4],
                    "sort_order": row[5],
                }
                for row in rows
            ]
        _fast_paths_cache = (now, items)
        return items
    except Exception as e:
        logger.warning("Gagal memuat chatbot_fast_paths dari DB: %s", str(e))
        return _fast_paths_cache[1] if _fast_paths_cache else []


def get_active_directories() -> list[dict[str, Any]]:
    """
    Mengambil seluruh data Direktori Unit/Bidang yang aktif dari tabel 'chatbot_directories'.
    Menggunakan cache in-memory 5 detik.
    """
    global _directories_cache
    now = time.time()
    if _directories_cache is not None and (now - _directories_cache[0]) < _CACHE_TTL_SECONDS:
        return _directories_cache[1]

    try:
        engine = get_engine()
        query = text(
            "SELECT id, nama_bidang, keywords, lokasi, email, layanan_utama, daftar_tugas, jam_operasional, sort_order "
            "FROM chatbot_directories WHERE is_active = 1 "
            "ORDER BY sort_order ASC, id ASC"
        )
        with engine.connect() as conn:
            rows = conn.execute(query).fetchall()
            items = []
            for row in rows:
                raw_tugas = row[6]
                parsed_tugas = []
                if raw_tugas:
                    try:
                        import json
                        if isinstance(raw_tugas, str):
                            parsed_tugas = json.loads(raw_tugas)
                        elif isinstance(raw_tugas, list):
                            parsed_tugas = raw_tugas
                    except Exception:
                        parsed_tugas = [t.strip() for t in str(raw_tugas).split("\n") if t.strip()]

                items.append({
                    "id": row[0],
                    "nama_bidang": row[1],
                    "keywords": [k.strip().lower() for k in (row[2] or "").split(",") if k.strip()],
                    "lokasi": row[3],
                    "email": row[4],
                    "layanan_utama": row[5],
                    "daftar_tugas": parsed_tugas,
                    "jam_operasional": row[7] or "Senin - Jumat (08:00 - 16:45 WIB)",
                    "sort_order": row[8],
                })
        _directories_cache = (now, items)
        return items
    except Exception as e:
        logger.warning("Gagal memuat chatbot_directories dari DB: %s", str(e))
        return _directories_cache[1] if _directories_cache else []


