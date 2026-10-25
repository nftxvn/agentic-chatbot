"""Titik masuk kompatibel untuk intent, normalisasi, data warga, dan kalkulasi.

Implementasi berada di app.services.routing. RAG dan pemanggil lama tetap
mengimpor fungsi di sini; cache anchor semantik hanya dimiliki routing.semantic.
"""

from app.services.routing.calendar import (
    _BULAN_INDONESIA,
    _NAMA_HARI,
    _NAMA_BULAN,
    _parse_date_from_text,
    _parse_days_count,
    parse_and_sum_durations_from_context,
    _calculate_calendar_difference,
    _format_human_duration,
    _enrich_facts_with_date_calculations,
    hitung_estimasi_selesai,
)
from app.services.routing.patterns import (
    _RE_SESSION_RECAP,
    _RE_CHITCHAT_CONVERSATIONAL,
    _RE_HUMAN_HANDOFF,
    _RE_GREETING,
    _RE_CALC_ESTIMASI_WAKTU,
    _RE_DOUBT_OR_CORRECTION,
    _is_doubt_or_correction_query,
)
from app.services.routing.language import (
    _SLANG_DICT,
    _FILLER_WORDS,
    _QUESTION_WORDS,
    _normalize_token,
    normalize_query,
    _matches_keywords,
    _is_interrogative_query,
)
from app.services.routing.semantic import (
    _norm_vector,
    _dot_vectors,
    _get_semantic_intent_vectors,
    classify_semantic_intent,
)
from app.services.routing.citizen import (
    _NAME_STOPWORDS,
    _INVALID_AGENCY_TERMS,
    _AGENCY_ALIASES,
    _clean_extracted_name,
    _clean_extracted_agency,
    extract_citizen_escalation_details,
)
from app.services.routing.dispatch import (
    route_intent,
)
