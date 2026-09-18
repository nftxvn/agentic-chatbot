"""
Database helper untuk koneksi MySQL menggunakan SQLAlchemy.
Digunakan untuk mengupdate status dokumen di database yang di-share dengan Laravel.
"""

import logging
import time
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)

# Engine SQLAlchemy (singleton, dibuat saat modul pertama kali diimpor)
_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Mendapatkan atau membuat SQLAlchemy engine (lazy loading).
    Menggunakan pool_pre_ping untuk menangani koneksi yang terputus.
    """
    global _engine
    if _engine is None:
        logger.info("Membuat koneksi database ke %s", settings.MYSQL_HOST)
        _engine = create_engine(
            settings.MYSQL_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,  # Recycle koneksi setiap 1 jam
        )
    return _engine


def update_document_status(
    document_id: int,
    status: str,
    **kwargs: Any,
) -> None:
    """
    Mengupdate status dokumen di tabel 'documents'.

    Args:
        document_id: ID dokumen yang akan diupdate.
        status: Status baru ('processing', 'completed', 'failed').
        **kwargs: Field tambahan yang bisa diupdate:
            - pdf_type (str): Tipe PDF ('text', 'scanned', 'mixed')
            - total_chunks (int): Jumlah total chunk yang dihasilkan
            - total_pages (int): Jumlah total halaman PDF
            - error_message (str): Pesan error jika gagal
            - processed_at (datetime): Waktu selesai diproses
    """
    engine = get_engine()

    # Bangun klausa SET secara dinamis berdasarkan kwargs
    set_clauses = ["status = :status", "updated_at = :updated_at"]
    params: dict[str, Any] = {
        "document_id": document_id,
        "status": status,
        "updated_at": datetime.utcnow(),
    }

    # Tambahkan field opsional jika ada
    allowed_fields = {
        "pdf_type",
        "total_chunks",
        "total_pages",
        "processed_pages",
        "error_message",
        "processed_at",
    }

    for key, value in kwargs.items():
        if key in allowed_fields:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
        else:
            logger.warning("Field '%s' tidak diizinkan untuk update, diabaikan.", key)

    # Susun query SQL
    set_clause_str = ", ".join(set_clauses)
    query = text(f"UPDATE documents SET {set_clause_str} WHERE id = :document_id")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params)
            conn.commit()
            logger.info(
                "Status dokumen %d diupdate ke '%s' (%d baris terpengaruh)",
                document_id,
                status,
                result.rowcount,
            )
    except Exception as e:
        logger.error(
            "Gagal mengupdate status dokumen %d: %s",
            document_id,
            str(e),
        )
        raise


def record_document_log(
    document_id: int,
    action: str,
    details: str | None = None,
    debounce_seconds: int = 15,
) -> None:
    """
    Mencatat log aktivitas dokumen ke tabel 'document_logs' dengan proteksi debounce.

    Args:
        document_id: ID dokumen.
        action: Kode aksi (misal 'ocr_completed', 'chunked', 'embedding_completed', 'completed').
        details: Catatan/keterangan aktivitas.
        debounce_seconds: Rentang waktu dalam detik untuk mencegah log duplikat beruntun.
    """
    engine = get_engine()
    now = datetime.utcnow()

    try:
        with engine.connect() as conn:
            # Cek log terakhir untuk dokumen ini
            check_query = text(
                "SELECT id, action, details, created_at FROM document_logs "
                "WHERE document_id = :document_id ORDER BY created_at DESC LIMIT 1"
            )
            row = conn.execute(check_query, {"document_id": document_id}).mappings().fetchone()

            if row and row["action"] == action:
                if row["created_at"]:
                    diff = (now - row["created_at"]).total_seconds()
                    if diff < debounce_seconds:
                        if details and row["details"] != details:
                            conn.execute(
                                text("UPDATE document_logs SET details = :details WHERE id = :id"),
                                {"details": details, "id": row["id"]},
                            )
                            conn.commit()
                        return

            insert_query = text(
                "INSERT INTO document_logs (document_id, action, details, created_at) "
                "VALUES (:document_id, :action, :details, :created_at)"
            )
            conn.execute(
                insert_query,
                {
                    "document_id": document_id,
                    "action": action,
                    "details": details,
                    "created_at": now,
                },
            )
            conn.commit()
            logger.info("Log aktivitas dokumen %d dicatat: '%s'", document_id, action)
    except Exception as e:
        logger.warning("Gagal mencatat log dokumen %d (%s): %s", document_id, action, e)


def get_all_documents() -> list[dict[str, Any]]:
    """
    Mengambil daftar semua dokumen dari tabel 'documents'.

    Returns:
        List of dict, setiap dict merepresentasikan satu baris dokumen.
    """
    engine = get_engine()

    query = text(
        "SELECT id, original_name, file_path, status, pdf_type, "
        "total_pages, total_chunks, created_at, updated_at "
        "FROM documents ORDER BY created_at DESC"
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.mappings().all()
            documents = [dict(row) for row in rows]
            logger.info("Berhasil mengambil %d dokumen dari database", len(documents))
            return documents

    except Exception as e:
        logger.error("Gagal mengambil daftar dokumen: %s", str(e))
        raise


def get_document_names(document_ids: Iterable[int]) -> dict[int, str]:
    """
    Mengambil Judul Dokumen (title) atau fallback ke nama berkas (original_name)
    untuk sekumpulan dokumen sekaligus.

    Dipakai untuk mengisi rujukan sumber / sitasi di jawaban chat RAG dan API
    agar menampilkan judul resmi dokumen seperti yang terlihat di Dashboard.

    Args:
        document_ids: Kumpulan ID dokumen. Duplikat diabaikan.

    Returns:
        Dict {document_id: title or original_name}. ID yang tidak ada di basis data
        tidak muncul di hasil.
    """
    ids = sorted({int(document_id) for document_id in document_ids})
    if not ids:
        return {}

    engine = get_engine()

    # expanding=True: SQLAlchemy yang menyusun daftar parameter untuk klausa IN,
    # sehingga nilainya tetap lewat jalur parameter dan tidak pernah dirangkai
    # ke dalam string SQL.
    query = text(
        "SELECT id, title, original_name FROM documents WHERE id IN :document_ids"
    ).bindparams(bindparam("document_ids", expanding=True))

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"document_ids": ids}).mappings().all()
            return {
                row["id"]: (
                    str(row["title"]).strip()
                    if row.get("title") and str(row.get("title")).strip()
                    else row["original_name"]
                )
                for row in rows
            }

    except Exception as e:
        logger.error("Gagal mengambil nama/judul untuk dokumen %s: %s", ids, str(e))
        raise


# Alias untuk kemudahan impor
get_document_names_by_ids = get_document_names


def get_document_by_id(document_id: int) -> dict[str, Any] | None:
    """
    Mengambil data satu dokumen berdasarkan ID.

    Args:
        document_id: ID dokumen yang dicari.

    Returns:
        Dict berisi data dokumen, atau None jika tidak ditemukan.
    """
    engine = get_engine()

    query = text(
        "SELECT d.id, d.original_name, d.file_path, d.status, d.pdf_type, "
        "d.category_id, d.total_pages, d.total_chunks, d.error_message, d.processed_at, "
        "d.created_at, d.updated_at, "
        "c.vision_prompt AS category_vision_prompt, "
        "c.vision_model AS category_vision_model, "
        "c.prompt_variables AS category_prompt_variables "
        "FROM documents d "
        "LEFT JOIN document_categories c ON d.category_id = c.id "
        "WHERE d.id = :document_id"
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"document_id": document_id})
            row = result.mappings().fetchone()

            if row is None:
                logger.info("Dokumen %d tidak ditemukan", document_id)
                return None

            document = dict(row)
            logger.info("Berhasil mengambil data dokumen %d", document_id)
            return document

    except Exception as e:
        logger.error(
            "Gagal mengambil data dokumen %d: %s",
            document_id,
            str(e),
        )
        raise


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


# ── Cache Dinamis untuk Fast-Path & Direktori (TTL 5 Detik) ──────
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


