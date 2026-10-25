"""Cache anchor semantik dan klasifikasi intent memakai encoder yang sama."""

import logging
import math

from app.services.routing.language import _is_interrogative_query

logger = logging.getLogger("app.services.tool_router")

_SEMANTIC_INTENT_VECTORS: dict[str, list[list[float]]] | None = None


def _norm_vector(v: list[float]) -> list[float]:
    """Normalisasi vektor L2 norm menggunakan pustaka standar math."""
    norm = math.sqrt(sum(float(x) * float(x) for x in v))
    if norm <= 0:
        return [float(x) for x in v]
    return [float(x) / norm for x in v]


def _dot_vectors(v1: list[float], v2: list[float]) -> float:
    """Dot product antara dua vektor."""
    return sum(float(a) * float(b) for a, b in zip(v1, v2))


def _get_semantic_intent_vectors() -> dict[str, list[list[float]]]:
    global _SEMANTIC_INTENT_VECTORS
    if _SEMANTIC_INTENT_VECTORS is None:
        try:
            from app.services.embedding_service import encode_texts

            anchors = {
                "human_escalation": [
                    "saya ingin menghubungi admin atau petugas dinas",
                    "hubungkan saya dengan admin atau staf bantuan helpdesk",
                    "bisa bicara dengan operator manusia atau staf asli",
                    "mau konsultasi dan chat langsung dengan tim customer service",
                    "tolong sambungkan saya ke staf piket atau admin diskominfo",
                    "alih kan percakapan ini ke operator manusia",
                    "saya butuh bantuan langsung dari staf manusia",
                    "apakah ada orang asli yang bisa saya ajak bicara",
                ],
                "chitchat": [
                    "halo hai assalamu'alaikum selamat pagi siang sore malam saleuem",
                    "apa kabar gimana sehat kabar baik sehat kamu gimana lagi apa lagi ngapain",
                    "nama saya perkenalkan nama saya kenalin panggil saya siapa kamu kamu siapa robot manusia",
                    "terima kasih makasih banyak matur nuwun syukron mantap keren good job semangat",
                ],
                "session_recap": [
                    "tadi kita bahas apa sih rangkum percakapan kita tadi ngomongin apa",
                    "sebelumnya saya tanya apa topik yang baru saja dibahas di obrolan",
                    "kita sedang bicara apa tadi tentang apa rangkuman percakapan",
                ],
            }
            res_map = {}
            for intent, texts in anchors.items():
                embs = encode_texts(texts)
                norm_embs = [_norm_vector(e) for e in embs]
                res_map[intent] = norm_embs
            _SEMANTIC_INTENT_VECTORS = res_map
        except Exception as e:
            logger.warning("Gagal memuat semantic intent vectors: %s", e)
            _SEMANTIC_INTENT_VECTORS = {}
    return _SEMANTIC_INTENT_VECTORS


def classify_semantic_intent(query: str) -> str | None:
    """
    Mengklasifikasikan intent pesan secara semantik menggunakan cosine similarity
    tanpa bergantung pada kata kunci statis.
    """
    vectors_map = _get_semantic_intent_vectors()
    if not vectors_map:
        return None
    try:
        from app.services.embedding_service import encode_query

        raw_vq = encode_query(query)
        if not raw_vq:
            return None
        vq = _norm_vector(raw_vq)

        scores = {}
        for intent, anchors in vectors_map.items():
            scores[intent] = max((_dot_vectors(vq, a) for a in anchors), default=0.0)

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Guard: Kalimat tanya informasi tidak boleh diklasifikasi sebagai eskalasi tiket bantuan
        if best_intent == "human_escalation" and best_score >= 0.80 and not _is_interrogative_query(query):
            return "human_escalation"
        if best_intent == "session_recap" and best_score >= 0.75:
            return "session_recap"
        if best_intent == "chitchat" and best_score >= 0.75:
            return "chitchat"
        return None
    except Exception as e:
        logger.warning("Error saat classify_semantic_intent: %s", e)
        return None


