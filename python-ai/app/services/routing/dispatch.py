"""Pemilihan jalur intent dengan urutan prioritas dan payload yang dipertahankan."""

import logging
import re
from typing import Any

from app.database import get_active_directories, get_active_fast_paths
from app.services.routing.patterns import (
    _RE_SESSION_RECAP,
    _RE_HUMAN_HANDOFF,
    _RE_GREETING,
    _RE_CHITCHAT_CONVERSATIONAL,
    _RE_CALC_ESTIMASI_WAKTU,
    _is_doubt_or_correction_query,
)
from app.services.routing.calendar import (
    _parse_days_count,
    _parse_date_from_text,
    _enrich_facts_with_date_calculations,
)
from app.services.routing.language import _is_interrogative_query, _matches_keywords
from app.services.routing.semantic import classify_semantic_intent
from app.services.routing.citizen import extract_citizen_escalation_details

logger = logging.getLogger("app.services.tool_router")

def route_intent(query: str, session_id: str | None = None) -> dict[str, Any]:
    """
    Menganalisis query pengguna dan menentukan jalur eksekusi:
    1. Fast-Path Chitchat / Sapaan (Bypass LLM < 0.05s)
    2. Tool Agent: Kalkulator Hari Kerja SOP (Matematika < 0.05s)
    3. Tool Agent: Pelacak Status Tiket Layanan (Ticket Tracker)
    4. Knowledge-Augmented Synthesis: Direktori Unit Kerja & Bidang (Prioritas Entitas Spesifik)
    5. Knowledge-Augmented Synthesis: Fast-Path FAQ Dinamis (Injeksi Fakta ke LLM)
    6. Default Fallback: Full Two-Stage RAG Knowledge Retrieval Pipeline
    """
    q = query.strip()

    # Resolusi konteks follow-up / kata ganti bila ada sesi aktif
    search_q = q
    is_context_resolved = False
    if session_id:
        try:
            from app.services.session_memory import resolve_contextual_query
            resolved_query, is_res = resolve_contextual_query(q, session_id)
            if is_res:
                search_q = resolved_query
                is_context_resolved = True
        except Exception as e:
            logger.debug("Gagal resolve contextual query: %s", e)

    q_lower = q.lower()
    search_lower = search_q.lower()
    is_question = _is_interrogative_query(q)

    # 0. AI-Native Semantic Intent Classifier (Deteksi Makna Semantik Tanpa Ketergantungan Keyword)
    sem_intent = classify_semantic_intent(q)
    if sem_intent == "session_recap" or _RE_SESSION_RECAP.search(q_lower) or _RE_SESSION_RECAP.search(search_lower):
        return {
            "intent": "session_recap",
            "params": {"raw_query": q},
            "label": "Rangkuman Memori Percakapan (Session Recap)",
        }

    # 0.1 Permintaan Handover / Eskalasi ke Petugas Manusia (Human Escalation)
    if _RE_HUMAN_HANDOFF.search(q_lower) or _RE_HUMAN_HANDOFF.search(search_lower) or (not is_question and sem_intent == "human_escalation"):
        return {
            "intent": "human_escalation",
            "params": {"raw_query": q},
            "label": "Permintaan Bantuan Petugas (Handover)",
        }

    # 0.2 Jalur Chitchat, Sapaan & Persona Asisten (Prioritaskan sapaan agar tidak disalahartikan sebagai rincian kendala)
    is_greeting_or_chitchat = bool(sem_intent == "chitchat" or _RE_GREETING.match(q_lower) or _RE_CHITCHAT_CONVERSATIONAL.search(q_lower))
    clean_intro_test = re.sub(r"[*_•\-]+", " ", q_lower)
    
    # Deteksi format form bantuan eksplisit
    is_structured_form = bool(re.search(
        r"(?:nama(?:\s*(?:saya|ku|lengkap))?\s*[:=]|instansi(?:\s*(?:\/|dan)\s*opd)?\s*[:=]|opd\s*[:=]|unit\s*kerja\s*[:=]|kendala(?:\s*(?:saya|kami))?\s*[:=]|keluhan(?:\s*(?:saya|kami))?\s*[:=]|masalah(?:\s*(?:saya|kami))?\s*[:=]|keperluan(?:\s*(?:saya|kami))?\s*[:=])",
        clean_intro_test
    ))
    is_natural_intro = bool(re.search(
        r"\b(?:perkenalkan\s+(?:nama\s+)?saya|nama\s+saya\s+[a-z]+|saya\s+[a-z\s'\.]+\s+dari\s+(?:dinas|badan|opd|bagian|bidang|kemen|kantor|puskesmas|rsud|setda|uin|usk)|kami\s+dari\s+(?:dinas|badan|opd|bagian|bidang|kemen|kantor))\b",
        q_lower
    ))
    is_explicit_intro = is_structured_form or is_natural_intro

    if is_greeting_or_chitchat and not is_explicit_intro:
        return {
            "intent": "chitchat",
            "params": {"raw_query": q},
            "label": "Percakapan Santai & Persona (Chitchat)",
        }

    # 0.3 Follow-up informasi tambahan (Nama/Instansi/Kendala) setelah Permintaan Handover
    # GUARD: Kalimat tanya normal TIDAK BOLEH memicu form eskalasi kecuali ada format key-value eksplisit
    if is_structured_form or (not is_question and (is_natural_intro or session_id)):
        try:
            from app.services.session_memory import get_last_context
            last_topic, _ = get_last_context(session_id) if session_id else (None, None)
            is_waiting_helpdesk = bool(
                last_topic and any(kw in last_topic.lower() for kw in ["bantuan petugas", "handover", "helpdesk", "petugas", "informasi tambahan"])
            )
            
            # Hanya ekstrak jika sesi memang menunggu bantuan petugas ATAU user secara eksplisit mengisi form/intro
            if is_waiting_helpdesk or is_explicit_intro:
                if not any(kw in q_lower for kw in ["sop", "perwal", "sk", "berapa", "kapan", "bagaimana cara", "hitung", "aturan", "regulasi", "pasal"]):
                    parsed_details = extract_citizen_escalation_details(q)
                    has_valid_info = bool(
                        parsed_details.get("citizen_name") or 
                        (parsed_details.get("citizen_agency") and parsed_details.get("issue_summary"))
                    )
                    if is_structured_form or has_valid_info:
                        return {
                            "intent": "human_escalation_followup",
                            "params": {
                                "raw_query": q,
                                "citizen_name": parsed_details["citizen_name"],
                                "citizen_agency": parsed_details["citizen_agency"],
                                "issue_summary": parsed_details["issue_summary"],
                            },
                            "label": "Informasi Tambahan untuk Tim Petugas",
                        }
        except Exception as e:
            logger.debug("Gagal evaluasi escalation follow-up: %s", e)

    # 1.5 Cek apakah query saat ini adalah koreksi/sanggahan atau follow-up dari topik RAG sebelumnya
    is_doubt = _is_doubt_or_correction_query(q) or _is_doubt_or_correction_query(search_q)
    if session_id and (is_doubt or is_context_resolved):
        try:
            from app.services.session_memory import get_last_context
            last_topic, last_entity = get_last_context(session_id)
            is_prev_rag = bool(
                last_topic and any(kw in last_topic.lower() for kw in ["sop", "dokumen", "prosedur", "perwal", "sk", "dpa", "renja", "renstra", "lkjip", "sakip", "iku", "pk"])
            ) or bool(
                last_entity and any(kw in last_entity.lower() for kw in ["sop", "dokumen", "prosedur", "perwal", "dinas", "surat", "tugas", "pelaksanaan", "pasal", "halaman"])
            )
            if is_doubt and is_prev_rag:
                logger.info("Doubt/Correction query pada topik RAG ('%s') -> prioritaskan Two-Stage RAG untuk verifikasi dokumen", last_topic)
                return {
                    "intent": "rag",
                    "params": {"query": search_q, "raw_query": q},
                    "label": "Two-Stage Knowledge Retrieval (RAG - Verifikasi Fakta Dokumen)",
                }
        except Exception as e:
            logger.debug("Gagal cek previous context: %s", e)

    # 2. Jalur Tool Agent: Kalkulator Estimasi Waktu
    if _RE_CALC_ESTIMASI_WAKTU.search(q_lower) or _RE_CALC_ESTIMASI_WAKTU.search(search_lower):
        days = _parse_days_count(search_q) or _parse_days_count(q)
        target_date = _parse_date_from_text(search_q) or _parse_date_from_text(q)
        if days is not None:
            return {
                "intent": "tool_calculator",
                "params": {
                    "lama_hari_kerja": days,
                    "tanggal_mulai": target_date.strftime("%Y-%m-%d") if target_date else None,
                },
                "label": "Tool Agent: Kalkulator Estimasi Waktu",
            }

    # 3. Jalur Direktori Bidang & Unit Kerja (DIPRIORITASKAN dari Fast-Path Umum)
    # Ini mencegah pertanyaan seperti "jam operasional bidang statistik" salah tangkap ke jam kerja umum.
    _SOP_GUARDS = ["berapa", "kapan", "waktu", "cara", "bagaimana", "syarat", "langkah", "prosedur", "alur", "sop", "mengurus", "urus", "bikin", "buat", "dokumen", "persyaratan", "berkas"]
    active_dirs = get_active_directories()
    for d in active_dirs:
        if _matches_keywords(q, d["keywords"]) or _matches_keywords(search_q, d["keywords"]):
            # Guard: Jika mengandung kata operasional/SOP, biarkan jatuh (fall-through) ke RAG!
            if any(g in q_lower or g in search_lower for g in _SOP_GUARDS):
                continue

            # Bangun konteks fakta spesifik unit kerja
            tugas_list = d.get("daftar_tugas") or []
            if isinstance(tugas_list, list):
                tugas_formatted = "\n".join([f"- {t}" for t in tugas_list])
            else:
                tugas_formatted = str(tugas_list)

            facts = (
                f"Informasi Unit Kerja Terverifikasi:\n"
                f"- Nama Bidang/Unit : {d['nama_bidang']}\n"
                f"- Lokasi Kantor   : {d['lokasi']}\n"
                f"- Email Resmi     : {d['email']}\n"
                f"- Layanan Utama   : {d['layanan_utama']}\n"
                f"- Jam Operasional : {d.get('jam_operasional', 'Senin - Jumat (08:00 - 16:45 WIB)')}\n"
                f"- Lingkup Tugas & Pelayanan:\n{tugas_formatted}"
            )

            return {
                "intent": "augmented_knowledge",
                "params": {
                    "facts_context": facts,
                    "source_title": d["nama_bidang"],
                    "category": "direktori",
                    "query": search_q,
                    "raw_query": q,
                },
                "label": f"Fakta Direktori: {d['nama_bidang']}",
            }

    # 5. Jalur Fast-Path & FAQ Dinamis dari Basis Data MySQL
    active_fast_paths = get_active_fast_paths()
    for fp in active_fast_paths:
        if _matches_keywords(q, fp["keywords"]) or _matches_keywords(search_q, fp["keywords"]):
            cat_label = fp.get("category", "general").upper()
            facts = (
                f"Informasi Resmi Instansi:\n"
                f"- Topik: {fp['title']}\n"
                f"- Rincian Informasi Resmi: {fp['response_text']}"
            )
            facts = _enrich_facts_with_date_calculations(facts)
            return {
                "intent": "augmented_knowledge",
                "params": {
                    "facts_context": facts,
                    "source_title": fp["title"],
                    "category": fp["category"],
                    "query": search_q,
                    "raw_query": q,
                },
                "label": f"Fakta Instansi [{cat_label}]: {fp['title']}",
            }

    # 6. Default Fallback: Full Two-Stage RAG Knowledge Retrieval Pipeline
    return {
        "intent": "rag",
        "params": {"query": search_q, "raw_query": q},
        "label": "Two-Stage Knowledge Retrieval (RAG)",
    }


