"""Orkestrasi chat RAG dan titik masuk kompatibel untuk router serta worker.

Retrieval, pemeriksaan konteks, prompt, dan streaming model berada di paket
app.services.rag. Helper tetap diekspor di sini untuk pemanggil yang ada.
"""

import logging
import re
from typing import Generator

from app.config import settings
from app.database import get_chatbot_rag_config
from app.services import session_memory, tool_router
from app.services.backend_client import dispatch_ticket_to_laravel as _dispatch_ticket_to_laravel
from app.services.rag.prompts import (
    _SYSTEM_PROMPT,
    _get_current_date_info,
    _get_institution_info,
)
from app.services.rag.grounding import (
    _context_is_sop_document,
    _context_has_full_procedure,
    _nomor_item_tertinggi,
    _entitas_tak_ada_di_konteks,
    _is_procedure_question,
    _jumlah_yang_disodorkan,
    _asks_for_complete_list,
    _enum_sort_key,
    _penanda_huruf_sah,
    _penanda_maju,
    _extract_enumeration_runs,
    _label_di_konteks,
    _kata_pembeda_label,
    _label_yang_ditanya,
    _label_yang_menaungi,
    _saring_menurut_label,
    _select_relevant_run,
    _build_enumeration_answer,
    _extract_list_items,
    _build_comparison_hint,
    _build_time_calculation_hint,
    _petunjuk_fokus_label,
    _is_list_query,
)
from app.services.rag.retrieval import (
    _TOP_K,
    _format_pages_list,
    _reciprocal_rank_fusion,
    invalidate_bm25_cache,
    _get_bm25_index,
    _build_where_filter,
    _retrieve_context,
)
from app.services.rag.generation import (
    _estimasi_token_konteks,
    _gagal_alokasi,
    _stream_jawaban,
)

logger = logging.getLogger(__name__)

_RE_DOUBT_OR_CORRECTION = re.compile(
    r"\b(salah|keliru|bukan|bukannya|kok beda|kok salah|kok bisa|kenapa beda|memang iya|masa sih|yakin|beneran|serius|ngaco|bohong|ngibul|gak bener|tidak benar|kurang tepat|tidak tepat|hitung kembali|hitung ulang)\b",
    re.IGNORECASE,
)


def _is_doubt_or_correction_query(text: str) -> bool:
    """Mendeteksi apakah pertanyaan pengguna adalah bentuk keraguan, sanggahan, atau koreksi jawaban sebelumnya."""
    if not text:
        return False
    return bool(_RE_DOUBT_OR_CORRECTION.search(text))


def generate_response(
    query: str,
    session_id: str,
    document_ids: list[int] | None = None,
    system_prompt_override: str | None = None,
    temperature_override: float | None = None,
    top_k_override: int | None = None,
    include_debug: bool = False,
) -> Generator[str | dict, None, None]:
    """
    Menghasilkan respons RAG secara streaming.

    Langkah-langkah:
    1. Ambil konfigurasi prompt & chatbot aktif dari database (atau override sandbox).
    2. Cari konteks relevan di ChromaDB.
    3. Jika include_debug aktif, kirim event metadata chunk terlebih dahulu.
    4. Jika pertanyaan minta prosedur tapi konteks cuma daftar nama SOP,
       jawab langsung tanpa perlu panggil LLM.
    5. Bangun prompt dengan konteks (+ tabel perbandingan jika relevan).
    6. Panggil LLM Ollama dan stream hasilnya.
    7. Sertakan referensi sumber di akhir bila diaktifkan.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat (untuk logging dan tracking).
        document_ids: Bila diisi, pencarian dibatasi hanya pada dokumen tersebut.
        system_prompt_override: Override system prompt (opsional, untuk playground sandbox).
        temperature_override: Override temperature (opsional, untuk playground sandbox).
        top_k_override: Override top-k retrieval (opsional, untuk playground sandbox).
        include_debug: Bila True, yield dict berisi chunks metadata sebelum teks jawaban.

    Yields:
        String atau Dict berisi chunk respons dan metadata debug.
    """
    logger.info(
        "Memulai generate response — session=%s, query='%s'",
        session_id,
        query[:80],
    )

    try:
        # 1. Ambil konfigurasi chatbot & RAG aktif
        rag_cfg = get_chatbot_rag_config()
        active_llm_model = rag_cfg.get("llm_model_name") or settings.LLM_MODEL_NAME
        chatbot_name = rag_cfg.get("chatbot_name", "Asisten Virtual Diskominfotik")
        chatbot_persona = rag_cfg.get("chatbot_persona", "Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh")

        raw_template = (
            system_prompt_override
            if system_prompt_override is not None and system_prompt_override.strip()
            else (rag_cfg.get("rag_system_prompt") or _SYSTEM_PROMPT)
        )

        active_prompt_template = raw_template.replace("{chatbot_name}", chatbot_name).replace("{chatbot_persona}", chatbot_persona)
        if chatbot_name and chatbot_name not in active_prompt_template:
            active_prompt_template = f"Identitas: {chatbot_name}\nPersona: {chatbot_persona}\n\n" + active_prompt_template

        temperature = (
            temperature_override
            if temperature_override is not None
            else rag_cfg.get("rag_temperature", 0.0)
        )
        active_top_k = (
            top_k_override
            if top_k_override is not None
            else rag_cfg.get("rag_top_k", _TOP_K)
        )
        active_num_ctx = int(rag_cfg.get("rag_num_ctx", settings.LLM_NUM_CTX))
        fallback_msg = rag_cfg.get("chatbot_fallback_message") or "Mohon maaf, informasi terkait hal tersebut belum tersedia di dalam dokumen SOP kami. Jika Anda ingin dibantu langsung oleh tim Diskominfotik, silakan beri tahu saya ya."
        citation_enabled = rag_cfg.get("rag_citation_enabled", True)

        # 2. Fast-Path Intent Routing & Agentic Tools dengan Context Memory
        chat_history = session_memory.get_session_history(session_id, max_turns=4)
        route_result = tool_router.route_intent(query, session_id=session_id)
        intent = route_result["intent"]
        route_label = route_result.get("label", "Fast-Path Routing")
        route_params = route_result.get("params", {})

        if intent == "human_escalation":
            extracted = tool_router.extract_citizen_escalation_details(query)
            c_name = extracted.get("citizen_name")
            c_agency = extracted.get("citizen_agency")
            c_issue = extracted.get("issue_summary")

            # Scan history session jika nama / instansi belum ditemukan di prompt saat ini
            if not c_name or not c_agency:
                for turn in chat_history:
                    if turn.get("role") == "user":
                        u_txt = turn.get("content", "")
                        hist_ext = tool_router.extract_citizen_escalation_details(u_txt)
                        if not c_name and hist_ext.get("citizen_name"):
                            c_name = hist_ext["citizen_name"]
                        if not c_agency and hist_ext.get("citizen_agency"):
                            c_agency = hist_ext["citizen_agency"]
                        if (not c_issue or c_issue == query) and hist_ext.get("issue_summary") and hist_ext["issue_summary"] != u_txt:
                            c_issue = hist_ext["issue_summary"]
                        elif (not c_issue or c_issue == query) and u_txt and not any(kw in u_txt.lower() for kw in ["halo", "hai", "selamat", "admin", "hubungi"]):
                            c_issue = f"Pertanyaan: {u_txt[:120]}"

            if c_name:
                greeting_target = f"Bapak/Ibu {c_name}" + (f" dari {c_agency}" if c_agency else "")
                handoff_msg = (
                    f"Baik {greeting_target}, permintaan Anda sedang saya teruskan ke Petugas Helpdesk Diskominfotik untuk dibantu lebih lanjut.\n\n"
                    "Jika ada detail kendala tambahan yang ingin disampaikan, silakan ketik langsung di sini ya.\n\n"
                    "Selain itu, Anda juga dapat berkonsultasi langsung di kantor Diskominfotik (Balai Kota Banda Aceh, Gedung C Lantai 3) atau Call Center 112. Terima kasih!"
                )
            else:
                handoff_msg = (
                    "Baik, permintaan Anda sedang saya teruskan ke Petugas Helpdesk Diskominfotik.\n\n"
                    "Agar petugas kami dapat langsung memproses kendala Anda dengan cepat, mohon balas dengan format singkat berikut:\n\n"
                    "📋 **Format Data Bantuan:**\n"
                    "• **Nama:** [Nama Lengkap Anda]\n"
                    "• **Instansi/OPD:** [Nama Dinas / Badan / Kantor / Kementerian]\n"
                    "• **Kendala:** [Rincian masalah / keperluan Anda]\n\n"
                    "*(Contoh: Nama: Naufal / Instansi: Kemenkes / Kendala: Uang makan belum cair)*\n\n"
                    "Selain itu, Anda juga dapat berkonsultasi langsung di kantor Diskominfotik (Balai Kota Banda Aceh, Gedung C Lantai 3) atau Call Center 112. Terima kasih!"
                )

            # Dispatch awal ke Laravel dengan metadata yang teridentifikasi
            _dispatch_ticket_to_laravel(
                session_id=session_id,
                message=query,
                intent="human_escalation",
                citizen_name=c_name,
                citizen_agency=c_agency,
                issue_summary=c_issue or query,
            )
            # Keep the conversation history available until Laravel has received
            # the extracted handoff details, then stop AI memory for this session.
            session_memory.clear_session(session_id)

            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": "Bantuan Tim Diskominfotik (Handover)",
                    "detail": "Pengguna meminta bantuan langsung dari tim manusia. Meneruskan ke antrean tindak lanjut...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": True,
                }
            yield handoff_msg
            return

        if intent == "human_escalation_followup":
            c_name = route_params.get("citizen_name")
            c_agency = route_params.get("citizen_agency")
            c_issue = route_params.get("issue_summary") or query

            if not c_name or not c_agency:
                for turn in chat_history:
                    if turn.get("role") == "user":
                        u_txt = turn.get("content", "")
                        hist_ext = tool_router.extract_citizen_escalation_details(u_txt)
                        if not c_name and hist_ext.get("citizen_name"):
                            c_name = hist_ext["citizen_name"]
                        if not c_agency and hist_ext.get("citizen_agency"):
                            c_agency = hist_ext["citizen_agency"]

            # Dispatch tindak lanjut info warga ke Laravel
            _dispatch_ticket_to_laravel(
                session_id=session_id,
                message=query,
                intent="human_escalation_followup",
                citizen_name=c_name,
                citizen_agency=c_agency,
                issue_summary=c_issue,
            )
            # Follow-up identity/issue details now belong to the human ticket,
            # so they should not remain in AI session memory either.
            session_memory.clear_session(session_id)

            greeting_target = f"Bapak/Ibu {c_name}" if c_name else "Bapak/Ibu"
            if c_agency:
                greeting_target += f" dari {c_agency}"

            followup_ack = (
                f"Terima kasih atas informasinya, {greeting_target}.\n\n"
                "Data identitas dan rincian kendala Anda sudah tersimpan dan otomatis disinkronkan ke antrean Petugas Helpdesk Diskominfotik. "
                "Petugas kami akan segera merespons pesan Anda di sini. Mohon ditunggu ya!"
            )
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": "Catatan Tambahan untuk Petugas",
                    "detail": "Menyimpan data identitas/kendala pengguna ke antrean tindak lanjut...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": True,
                }
            yield followup_ack
            return

        if intent == "session_recap":
            is_empty_history = not chat_history or len(chat_history) == 0
            if is_empty_history:
                recap_msg = (
                    "Kita baru saja memulai sesi percakapan ini dan belum membahas topik tertentu. "
                    "Ada informasi seputar layanan atau dokumen SOP di Diskominfotik Kota Banda Aceh yang dapat saya bantu?"
                )
                if include_debug:
                    yield {
                        "type": "trace",
                        "stage": "intent_routing",
                        "step": 1,
                        "total_steps": 1,
                        "label": "Rangkuman Memori Sesi",
                        "detail": "Sesi belum memiliki riwayat obrolan terdahulu.",
                    }
                    yield {
                        "type": "debug",
                        "chunks": [],
                        "total_chunks": 0,
                    }
                    yield {
                        "type": "telemetry",
                        "model_name": active_llm_model,
                        "context_tokens": 0,
                        "num_ctx": active_num_ctx,
                        "chunks_count": 0,
                        "is_fallback": False,
                    }
                session_memory.add_user_message(session_id, query)
                session_memory.add_assistant_message(session_id, recap_msg, topic="Rangkuman Sesi")
                yield recap_msg
                return

            history_lines = []
            for m in chat_history:
                role_label = "Pengguna" if m.get("role") == "user" else "Asisten"
                content_text = m.get("content", "").strip()
                if content_text:
                    history_lines.append(f"{role_label}: {content_text}")

            history_formatted = "\n".join(history_lines)

            recap_prompt = f"""Anda adalah Asisten Virtual resmi Diskominfotik Kota Banda Aceh.
Pengguna menanyakan apa yang telah dibahas sebelumnya dalam percakapan ini.

Riwayat Percakapan yang Telah Berlangsung:
{history_formatted}

Instruksi:
1. Rangkum secara singkat, jelas, santun, dan bersahabat topik atau pertanyaan yang baru saja dibahas oleh pengguna di atas dalam 1-2 kalimat ringkas.
2. Akhiri dengan menawarkan bantuan lebih lanjut seputar layanan atau SOP Diskominfotik Kota Banda Aceh.
3. JANGAN mengarang informasi di luar riwayat percakapan di atas.
4. JANGAN menggunakan emoji."""

            estimasi_recap = _estimasi_token_konteks(recap_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": "Rangkuman Memori Sesi",
                    "detail": f"Membaca {len(chat_history)} pesan terdahulu dan merangkum obrolan...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                recap_prompt,
                query,
                temperature=0.2,
                num_ctx=active_num_ctx,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_recap = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_recap, topic="Rangkuman Sesi")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": estimasi_recap,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "chitchat":
            is_simple_hi = bool(re.match(r"^(?:halo|hai|hay|hei|heyy|hi|hello|helo|hoi|hoy|oy|oi|woy|woi|uy|yo|assalamu['\s]?alaikum|ass|askum|saleuem|saleum|kru\s+seumangat|p|ping|tes|test)[\s,.-]*$", query.strip().lower()))
            is_followup = bool(chat_history and len(chat_history) > 0)

            if is_simple_hi and not is_followup:
                greeting_msg = rag_cfg.get("chatbot_greeting") or (
                    f"Halo! Saya adalah {chatbot_persona}. "
                    "Ada yang bisa saya bantu mengenai informasi SOP atau layanan Diskominfotik Kota Banda Aceh?"
                )
                if include_debug:
                    yield {
                        "type": "trace",
                        "stage": "intent_routing",
                        "step": 1,
                        "total_steps": 1,
                        "label": route_label,
                        "detail": "Input terdeteksi sebagai sapaan awal. Menjawab langsung...",
                    }
                    yield {
                        "type": "debug",
                        "chunks": [],
                        "total_chunks": 0,
                    }
                    yield {
                        "type": "telemetry",
                        "model_name": active_llm_model,
                        "context_tokens": 0,
                        "num_ctx": active_num_ctx,
                        "chunks_count": 0,
                        "is_fallback": False,
                    }
                session_memory.add_user_message(session_id, query)
                session_memory.add_assistant_message(session_id, greeting_msg, topic="Sapaan")
                yield greeting_msg
                return

            now_str = _get_current_date_info()
            inst_info_str = _get_institution_info()

            chitchat_prompt = f"""Anda adalah Asisten Virtual resmi Layanan Informasi Diskominfotik Kota Banda Aceh ({chatbot_name}) yang ramah, hangat, manusiawi, santun, dan profesional.

Waktu Acuan: {now_str}
Profil Singkat Instansi:
{inst_info_str}

Instruksi Komunikasi:
1. Respon percakapan santai pengguna (sapaan, tanya kabar/kondisi, apresiasi, atau pertanyaan identitas diri) secara ramah, natural, dan menyenangkan layaknya petugas Front Office yang melayani masyarakat.
2. Bila pengguna menanyakan kabar (misal: 'kamu gimana sehat?', 'apa kabar?'), jawab dengan ramah bahwa Anda dalam kondisi sangat baik dan siap membantu.
3. Bila pengguna menanyakan identitas/kemampuan (misal: 'kamu siapa?', 'bisa apa aja?'), jelaskan secara ringkas peran Anda sebagai asisten resmi yang membantu masyarakat dan ASN dalam mencari informasi SOP kedinasan dan layanan Diskominfotik Kota Banda Aceh.
4. Bila pengguna mengucapkan terima kasih/apresiasi, balas dengan ramah dan tulus.
5. Akhiri dengan menawarkan bantuan seputar layanan atau dokumen SOP Diskominfotik Kota Banda Aceh.
6. JANGAN memunculkan pesan 'tidak ditemukan di dokumen SOP' untuk obrolan santai ini.
7. JANGAN menggunakan emoji."""

            estimasi_chitchat = _estimasi_token_konteks(chitchat_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": "Obrolan Santai & Persona",
                    "detail": "Menjawab percakapan santai secara natural berbasis persona helpdesk...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                chitchat_prompt,
                query,
                temperature=0.3,
                num_ctx=active_num_ctx,
                chat_history=chat_history,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_resp = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_resp, topic="Percakapan Santai")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": estimasi_chitchat,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "augmented_knowledge":
            facts = route_params.get("facts_context", "")
            source_title = route_params.get("source_title", "Informasi Resmi")
            category = route_params.get("category", "instansi")
            now_str = _get_current_date_info()
            is_followup = bool(chat_history and len(chat_history) > 0)

            salam_guide = (
                "1. Percakapan Lanjutan (Multi-Turn): Karena ini adalah pertanyaan lanjutan dalam sesi percakapan yang sedang berjalan, JANGAN mengulang salam pembuka formal atau kalimat 'selamat datang' yang sama. Jawab langsung ke inti pertanyaan secara santun dan jelas."
                if is_followup
                else "1. Awali dengan salam pembuka yang ramah dan sopan (misal: 'Assalamu\\'alaikum / Halo, selamat datang di Layanan Informasi Diskominfotik Kota Banda Aceh')."
            )

            is_correction = _is_doubt_or_correction_query(query)
            if is_correction:
                apology_guide = (
                    "3. Penanganan Koreksi & Keraguan Pengguna: Karena pengguna meragukan atau mengoreksi jawaban sebelumnya:\n"
                    "   - Bersikaplah rendah hati, santun, dan profesional.\n"
                    "   - Awali dengan permohonan maaf atas kekeliruan sebelumnya secara santun (misal: 'Mohon maaf atas kekeliruan sebelumnya...').\n"
                    "   - Jelaskan perbaikan atau data yang benar dan akurat.\n"
                    "   - JANGAN menggunakan kata 'Tentu' saat meralat kesalahan sendiri.\n"
                    "   - JANGAN mengucapkan salam balasan jika pengguna tidak mengucapkan salam."
                )
            else:
                apology_guide = (
                    "3. Penjelasan Lugas & To-the-point: Jawab langsung pertanyaan pengguna secara lugas, santun, dan akurat berdasarkan Fakta Resmi di atas.\n"
                    "   - JANGAN meminta maaf dan JANGAN mengucapkan 'Mohon maaf atas kekeliruan' karena pengguna hanya mengajukan pertanyaan normal / pertanyaan lanjutan baru."
                )

            system_prompt = f"""Anda adalah Asisten Helpdesk dan Layanan Informasi Publik resmi Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh.
Tugas Anda adalah melayani masyarakat dan ASN dengan ramah, komunikatif, solutif, dan profesional layaknya petugas helpdesk / front office resmi.

WAKTU & TANGGAL ACUAN SAAT INI:
- Hari & Tanggal Hari Ini: {now_str}

FAKTA RESMI INSTANSI TERVERIFIKASI:
{facts}

PANDUAN KOMUNIKASI HELPDESK:
{salam_guide}
2. Sampaikan informasi inti secara jelas, lugas, dan akurat berdasarkan Fakta Resmi di atas.
{apology_guide}
4. Perhitungan Durasi Waktu: Bila pengguna menanyakan durasi/lama waktu sampai hari ini (misal 'sudah berapa hari/bulan/tahun menjabat'), hitung selisih waktu secara akurat dari tanggal peristiwa ke Hari & Tanggal Hari Ini ({now_str}).
5. Akhiri dengan kalimat penutup khas helpdesk yang ramah dan menawarkan bantuan lanjutan jika diperlukan (misal: 'Ada yang dapat kami bantu lagi terkait layanan Diskominfotik?').
6. Bila pertanyaan menggunakan Bahasa Aceh (misal: 'Saleuem', 'soe nan...', 'pat kanto...'), pahami maksudnya dan respon secara santun dalam Bahasa Indonesia dengan salam santun khas Aceh.
7. JANGAN menggunakan emoji atau karakter grafis.
8. ATURAN WAJIB (ANTI-HALUSINASI): Jawab HANYA menggunakan informasi yang tertulis secara eksplisit pada blok FAKTA RESMI INSTANSI TERVERIFIKASI di atas.
9. JIKA fakta di atas TIDAK memuat jawaban atau angka yang ditanyakan pengguna, ANDA WAJIB menjawab: "Maaf, informasi spesifik mengenai hal tersebut tidak tercantum dalam wawasan saya." DILARANG KERAS menggunakan wawasan umum Anda untuk menebak atau mengarang prosedur/angka/jadwal."""

            estimasi_token = _estimasi_token_konteks(system_prompt)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 2,
                    "label": route_label,
                    "detail": f"Menginjeksi fakta resmi [{source_title}] ke model {active_llm_model}...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "trace",
                    "stage": "generation",
                    "step": 2,
                    "total_steps": 2,
                    "label": "Sintesis Pengetahuan AI",
                    "detail": f"Menghasilkan respons natural berbasis fakta terverifikasi (~{estimasi_token} token)...",
                }

            response_chunks = []
            for chunk in _stream_jawaban(
                system_prompt,
                query,
                temperature=temperature,
                num_ctx=active_num_ctx,
                chat_history=chat_history,
                model_name=active_llm_model,
            ):
                response_chunks.append(chunk)
                yield chunk

            full_resp = "".join(response_chunks)
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(
                session_id,
                full_resp,
                topic=source_title,
                entity=route_params.get("search_query") or source_title,
            )

            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": f"{active_llm_model} (Fakta Instansi: {source_title})",
                    "context_tokens": estimasi_token,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            return

        if intent == "tool_calculator":
            calc_result = tool_router.hitung_estimasi_selesai(**route_params)
            if include_debug:
                yield {
                    "type": "trace",
                    "stage": "intent_routing",
                    "step": 1,
                    "total_steps": 1,
                    "label": route_label,
                    "detail": f"Mengeksekusi kalkulator hari kerja ({calc_result['lama_hari_kerja']} hari kerja)...",
                }
                yield {
                    "type": "debug",
                    "chunks": [],
                    "total_chunks": 0,
                }
                yield {
                    "type": "telemetry",
                    "model_name": f"{active_llm_model} (Tool: Kalkulator)",
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, calc_result["formatted_text"], topic="Kalkulator Hari Kerja")
            yield calc_result["formatted_text"]
            return

        resolved_query = route_params.get("query", query)
        corrected_query = tool_router.normalize_query(resolved_query) or resolved_query

        if include_debug:
            yield {
                "type": "trace",
                "stage": "retrieval",
                "step": 1,
                "total_steps": 3,
                "label": "Pencarian Vektor & BM25",
                "detail": "Mencari kandidat konteks di ChromaDB dan indeks leksikal...",
            }
            context_text, sources_text, debug_chunks = _retrieve_context(
                corrected_query,
                original_query=resolved_query,
                document_ids=document_ids,
                top_k_override=active_top_k,
                return_chunks_info=True,
            )
            yield {
                "type": "debug",
                "chunks": debug_chunks,
                "total_chunks": len(debug_chunks),
            }
            yield {
                "type": "trace",
                "stage": "ranking",
                "step": 2,
                "total_steps": 3,
                "label": "BGE-Reranker & RRF Ranking",
                "detail": f"Menghitung skor relevansi CrossEncoder dan merangking {len(debug_chunks)} potongan konteks...",
            }
        else:
            context_text, sources_text = _retrieve_context(
                corrected_query,
                original_query=resolved_query,
                document_ids=document_ids,
                top_k_override=active_top_k,
                return_chunks_info=False,
            )

        facts_context = route_params.get("facts_context", "")
        if facts_context:
            # Plan B: Gabungkan fakta instansi dari Fast-Path dengan dokumen PDF
            context_text = f"{facts_context}\n\n{context_text}"

        if not context_text.strip():
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": 0,
                    "num_ctx": active_num_ctx,
                    "chunks_count": 0,
                    "is_fallback": False,
                }
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, fallback_msg, topic="Fallback")
            yield fallback_msg
            return

        # Guard: pertanyaan menyebut entitas bernomor yang tidak ada di dokumen
        # (Diktum KEEMPAT, langkah ke-11). Dipasang PALING AWAL karena jalur
        # daftar terprogram di bawah menjawab tanpa melibatkan LLM sama sekali,
        # sehingga tidak ada tahap lain yang berkesempatan menyadari premisnya
        # palsu — ditanya Diktum KEEMPAT, ia pernah memuntahkan 74 SOP milik
        # Diktum KEDUA dengan penuh percaya diri.
        entitas = _entitas_tak_ada_di_konteks(resolved_query, context_text)
        if entitas is not None:
            logger.info("Premis palsu: %s tidak ada di konteks", entitas)
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            msg = (
                f"Maaf, {entitas} tidak ditemukan di dalam dokumen. "
                "Pastikan penomorannya sesuai dengan isi dokumen."
            )
            if sources_text and citation_enabled:
                msg += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, msg, topic="Entitas Tidak Ditemukan")
            yield msg
            return

        # Guard: pertanyaan minta prosedur, tapi konteks yang ditemukan cuma
        # daftar nama SOP (tanpa rincian) → jangan biarkan LLM mengarang.
        if (
            _is_procedure_question(resolved_query)
            and _context_is_sop_document(context_text)
            and not _context_has_full_procedure(context_text)
        ):
            logger.info("Konteks hanya berisi daftar nama SOP, bukan rincian prosedur — jawab langsung tanpa LLM.")
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            msg = "Dokumen hanya menyebutkan SOP ini sebagai salah satu item dalam daftar, namun tidak memuat rincian prosedurnya."
            if sources_text and citation_enabled:
                msg += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, msg, topic="Daftar SOP")
            yield msg
            return

        # Guard: pertanyaan meminta daftar UTUH dan dokumen memuat daftar panjang
        # yang relevan → kirim daftarnya apa adanya. Model lokal terbukti
        # memotong daftar 74 item di sekitar item ke-46, dan tidak ada cara dari
        # sisi prompt maupun konteks yang memperbaikinya (lihat
        # _build_enumeration_answer).
        jawaban_daftar = _build_enumeration_answer(context_text, resolved_query)
        if jawaban_daftar is not None:
            if include_debug:
                yield {
                    "type": "telemetry",
                    "model_name": active_llm_model,
                    "context_tokens": _estimasi_token_konteks(context_text),
                    "num_ctx": active_num_ctx,
                    "chunks_count": len(debug_chunks),
                    "is_fallback": False,
                }
            full_enum_resp = jawaban_daftar
            if sources_text and citation_enabled:
                full_enum_resp += f"\n\n**Sumber Referensi:**\n{sources_text}"
            session_memory.add_user_message(session_id, query)
            session_memory.add_assistant_message(session_id, full_enum_resp, topic="Daftar SOP")
            yield jawaban_daftar
            if sources_text and citation_enabled:
                yield f"\n\n**Sumber Referensi:**\n{sources_text}"
            return

        context_text = _build_comparison_hint(context_text, resolved_query)
        context_text = _build_time_calculation_hint(context_text, resolved_query)
        context_text += _petunjuk_fokus_label(resolved_query, context_text)

        now_str = _get_current_date_info()
        is_followup = bool(chat_history and len(chat_history) > 0)
        salam_inst = (
            "   - Percakapan Lanjutan (Multi-Turn): Karena ini adalah pertanyaan lanjutan dalam percakapan yang sedang berjalan, JANGAN mengulang salam pembuka formal atau ucapan 'selamat datang'. Langsung jawab ke inti pertanyaan secara santun."
            if is_followup
            else "   - Percakapan Awal: Awali dengan salam pembuka yang sopan dan ramah (misal: 'Assalamu\\'alaikum / Halo, selamat datang di Layanan Informasi Diskominfotik Kota Banda Aceh')."
        )

        formatted_template = (
            active_prompt_template
            .replace("{current_date}", now_str)
            .replace("{salam_guide}", salam_inst)
            .replace("{institution_info}", _get_institution_info())
        )

        if "{institution_info}" not in active_prompt_template and "Profil Instansi Terkini" not in formatted_template and "Informasi Dasar Instansi" not in formatted_template:
            formatted_template = f"{formatted_template}\n\nProfil Instansi Terkini:\n{_get_institution_info()}"



        if "{context}" in formatted_template:
            system_prompt = formatted_template.replace("{context}", context_text)
        else:
            system_prompt = f"{formatted_template}\n\nKonteks Dokumen Resmi:\n{context_text}"

        is_doubt = _is_doubt_or_correction_query(query) or _is_doubt_or_correction_query(resolved_query)
        if is_doubt:
            doubt_guide = (
                "\n\nInstruksi Khusus Penanganan Keraguan & Sanggahan Pengguna:\n"
                "- Pengguna sedang menyanggah, meragukan, atau meminta penegasan atas jawaban sebelumnya.\n"
                "- Periksa dan cocokkan secara seksama dengan Konteks Dokumen Resmi di atas.\n"
                "- Jika jawaban sebelumnya SUDAH BENAR dan sesuai isi dokumen, tegaskan kembali secara santun dengan menunjukkan bukti langkah dan durasi dari dokumen (JANGAN mengubah angka atau memodifikasi rincian SOP hanya karena disanggah pengguna).\n"
                "- Jika jawaban sebelumnya terdapat kekeliruan perhitungan/salah baca dokumen, akui dan sampaikan rincian yang benar sesuai dokumen resmi secara santun.\n"
                "- DILARANG KERAS mengarang, memodifikasi durasi menit/jam, atau mengubah nama pelaksana di luar fakta dokumen."
            )
            system_prompt += doubt_guide

        estimasi_token = _estimasi_token_konteks(system_prompt)
        logger.info(
            "Jendela konteks aktif: %d token (taksiran konteks %d token / %d karakter)",
            active_num_ctx, estimasi_token, len(system_prompt),
        )

        if include_debug:
            yield {
                "type": "trace",
                "stage": "generation",
                "step": 3,
                "total_steps": 3,
                "label": "Inferensi LLM",
                "detail": f"Mengirim konteks (~{estimasi_token} token, num_ctx={active_num_ctx}) ke model {active_llm_model}...",
            }

        response_chunks = []
        for chunk in _stream_jawaban(
            system_prompt,
            resolved_query,
            temperature=temperature,
            num_ctx=active_num_ctx,
            chat_history=chat_history,
            model_name=active_llm_model,
        ):
            response_chunks.append(chunk)
            yield chunk

        if sources_text and citation_enabled:
            ref_chunk = f"\n\n**Sumber Referensi:**\n{sources_text}"
            response_chunks.append(ref_chunk)
            yield ref_chunk

        full_rag_resp = "".join(response_chunks)
        
        # Ekstrak label SOP nyata dari konteks atau sumber rujukan
        context_labels = _label_di_konteks(context_text) if context_text else []
        best_label = context_labels[0] if context_labels else ""
        if not best_label and sources_text:
            first_src = sources_text.strip().split("\n")[0].lstrip("- *# ")
            if "SOP" in first_src or "Halaman" in first_src:
                best_label = first_src

        prev_topic, prev_entity = session_memory.get_last_context(session_id)
        
        # Cek apakah query saat ini adalah meta query
        meta_words = ["hitung", "kembali", "hari apa", "kapan", "siapa", "dimana", "tadi", "lanjut", "bisa", "koreksi", "ulang"]
        is_meta_query = any(mw in query.lower() for mw in meta_words) and len(query.split()) <= 5

        if is_meta_query and prev_entity and len(prev_entity) >= 3 and not any(mw in prev_entity.lower() for mw in ["hitung", "kembali", "hari apa"]):
            active_entity = prev_entity
        else:
            active_entity = best_label or prev_entity or resolved_query

        extracted_topic = best_label or prev_topic or "Dokumen SOP"

        session_memory.add_user_message(session_id, query)
        session_memory.add_assistant_message(
            session_id,
            full_rag_resp,
            topic=extracted_topic,
            entity=active_entity,
        )

        if include_debug:
            yield {
                "type": "telemetry",
                "model_name": active_llm_model,
                "context_tokens": estimasi_token,
                "num_ctx": active_num_ctx,
                "chunks_count": len(debug_chunks),
                "is_fallback": False,
            }

        logger.info("Respons berhasil di-generate untuk session %s", session_id)

    except Exception:
        # Rincian exception ditahan di log, tidak dikirim ke pengguna: pesan
        # mentah dari Ollama/ChromaDB kerap memuat URL internal dan path berkas.
        logger.error(
            "Gagal generate respons (session=%s)",
            session_id,
            exc_info=True,
        )
        yield (
            "\n\nTerjadi kesalahan saat memproses pertanyaan Anda. "
            "Silakan coba lagi; bila berulang, hubungi administrator."
        )
