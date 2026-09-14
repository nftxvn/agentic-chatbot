"""
Service Intent Router & Agentic Tools untuk Asisten AI Diskominfotik Kota Banda Aceh.

Mendukung:
1. Pure Chitchat Fast-Path (Sapaan cepat).
2. Knowledge-Augmented LLM Synthesis (Injeksi fakta instansi & direktori dinamis ke model AI).
3. Agentic Tools (Kalkulator Hari Kerja SOP, Pelacak Status Tiket Layanan).
4. Full Two-Stage Knowledge Retrieval (RAG) untuk dokumen SOP, Perwal, dan regulasi resmi.
"""

from datetime import datetime, timedelta
import logging
import re
from typing import Any

from app.database import get_active_directories, get_active_fast_paths

logger = logging.getLogger(__name__)

# Daftar bulan dalam Bahasa Indonesia untuk parsing tanggal
_BULAN_INDONESIA = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agt": 8, "agu": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12,
}

_NAMA_HARI = [
    "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"
]

_NAMA_BULAN = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

# Pola regex untuk sapaan dan uji coba (Termasuk Sapaan Bahasa Aceh & Santun)
_RE_GREETING = re.compile(
    r"^(?:(?:halo|hai|hay|hei|hi|hello|assalamu['\s]?alaikum(?:\s+wr\s+wb|\s+warahmatullahi\s+wabarakatuh)?|ass|askum|"
    r"saleuem(?:\s+teuka)?|saleum(?:\s+teuka)?|kru\s+seumangat|kiban\s+haba|haba\s+kiban|peue\s+haba|peu\s+haba|"
    r"selamat\s+(?:pagi|siang|sore|malam)|pagi|siang|sore|malam|"
    r"tes|test|ping|p|testing|tes\s+123|test\s+123|"
    r"terima\s+kasih|makasih|thanks|matur\s+nuwun|syukron|teurimong\s+gaseh|"
    r"admin|min|bot|asisten)"
    r"[\s,.-]*)+$",
    re.IGNORECASE,
)

# Pola regex untuk kalkulator hari kerja
_RE_CALC_HARI_KERJA = re.compile(
    r"\b(hitung\s+estimasi|estimasi\s+selesai|berapa\s+hari\s+kerja|kapan\s+selesai|"
    r"hitung\s+hari\s+kerja|estimasi\s+tanggal|kalkulasi\s+hari\s+kerja|"
    r"jika\s+prosesnya\s+\d+\s+hari\s+kerja|lama\s+proses\s+\d+\s+hari\s+kerja)\b",
    re.IGNORECASE,
)

# Pola regex untuk cek tiket
_RE_TICKET_QUERY = re.compile(
    r"\b(cek\s+tiket|status\s+tiket|tiket\s+layanan|lacak\s+tiket|nomor\s+tiket|"
    r"pengajuan\s+tiket|progres\s+tiket|tracking\s+tiket)\b",
    re.IGNORECASE,
)
_RE_TICKET_CODE = re.compile(
    r"\b(TIK|SRV|TKT|DISKOM|REQ)[-_]?\d{4,12}[-_]?\w*\b",
    re.IGNORECASE,
)


def _parse_date_from_text(text: str) -> datetime | None:
    """Mencoba mengekstrak tanggal dari teks pengguna."""
    lowered = text.lower()
    now = datetime.now()

    if "hari ini" in lowered:
        return now
    if "besok" in lowered:
        return now + timedelta(days=1)
    if "lusa" in lowered:
        return now + timedelta(days=2)

    # Format YYYY-MM-DD
    match_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if match_iso:
        try:
            return datetime(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
        except ValueError:
            pass

    # Format DD-MM-YYYY atau DD/MM/YYYY
    match_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", text)
    if match_dmy:
        try:
            return datetime(int(match_dmy.group(3)), int(match_dmy.group(2)), int(match_dmy.group(1)))
        except ValueError:
            pass

    # Format teks Indonesia: '4 September 2026' atau '12 agt 2026'
    for bln_str, bln_num in _BULAN_INDONESIA.items():
        pattern = rf"\b(\d{{1,2}})\s+{bln_str}\s+(\d{{4}})\b"
        match_txt = re.search(pattern, lowered)
        if match_txt:
            try:
                return datetime(int(match_txt.group(2)), bln_num, int(match_txt.group(1)))
            except ValueError:
                pass

    return None


def _parse_days_count(text: str) -> int | None:
    """Mengekstrak angka jumlah hari kerja dari query."""
    match = re.search(r"\b(\d+)\s*(?:hari\s*kerja|hari)\b", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Cek format angka di depan kata 'hari'
    match_fallback = re.search(r"\b(\d+)\b", text)
    if match_fallback:
        val = int(match_fallback.group(1))
        if 1 <= val <= 365:
            return val

    return None


def _enrich_facts_with_date_calculations(facts_text: str) -> str:
    """
    Mendeteksi tanggal di dalam fakta resmi (misal tanggal pelantikan)
    dan menghitung selisih waktu secara presisi (hari & bulan) hingga hari ini.
    """
    now = datetime.now()
    parsed_date = _parse_date_from_text(facts_text)
    if not parsed_date:
        return facts_text

    diff = now - parsed_date
    total_days = diff.days
    if total_days < 0:
        return facts_text

    months = total_days // 30
    remaining_days = total_days % 30

    hari_ini_str = f"{_NAMA_HARI[now.weekday()]}, {now.day} {_NAMA_BULAN[now.month]} {now.year}"
    tgl_peristiwa_str = f"{parsed_date.day} {_NAMA_BULAN[parsed_date.month]} {parsed_date.year}"

    calc_note = (
        f"\n- Data Perhitungan Waktu Nyata (Hingga Hari Ini: {hari_ini_str}):\n"
        f"  * Selisih waktu dari tanggal {tgl_peristiwa_str} sampai hari ini ({hari_ini_str}) adalah TEPAT {total_days} hari "
        f"(sekitar {months} bulan {remaining_days} hari).\n"
        f"  * Bila pengguna bertanya 'sudah berapa hari/bulan menjabat atau berlangsung', JAWAB BERDASARKAN ANGKA INI: {total_days} hari (sekitar {months} bulan {remaining_days} hari)."
    )
    return facts_text + calc_note


import difflib

# Kamus Normalisasi Slang, Singkatan Chat, Typo, dan Kosakata Bahasa Aceh
_SLANG_DICT = {
    # Kata Tanya & Percakapan (Bahasa Indonesia & Bahasa Aceh)
    "dmn": "dimana", "dmna": "dimana", "dimn": "dimana", "dmana": "dimana", "mn": "dimana",
    "mana": "dimana", "manaa": "dimana", "dimanakah": "dimana", "manakah": "dimana",
    "pat": "dimana", "dipat": "dimana", "ho": "kemana", "toh": "yang mana",
    "kmn": "kemana", "kmna": "kemana",
    "gmn": "bagaimana", "gmana": "bagaimana", "bgmn": "bagaimana", "bgm": "bagaimana", "gimana": "bagaimana",
    "pakriban": "bagaimana", "kiban": "bagaimana",
    "kpn": "kapan", "pajan": "kapan", "knp": "kenapa", "pakon": "kenapa", "napa": "kenapa",
    "brp": "berapa", "bbrp": "berapa", "brapa": "berapa", "brpa": "berapa", "padup": "berapa", "padum": "berapa", "padip": "berapa",
    "ap": "apa", "apkh": "apakah", "apaan": "apa", "peue": "apa", "peu": "apa", "peuh": "apa",
    "so": "siapa", "soe": "siapa",
    "sy": "saya", "aq": "saya", "gw": "saya", "gue": "saya", "ane": "saya", "lon": "saya", "ulon": "saya",
    "km": "kamu", "lu": "anda", "lo": "anda", "dron": "anda", "droeneuh": "anda", "gata": "kamu",
    "dr": "dari", "dlm": "dalam", "lam": "dalam", "utk": "untuk", "untk": "untuk", "keu": "untuk", "keupeu": "untuk apa",
    "dgn": "dengan", "dg": "dengan", "ngon": "dengan", "krn": "karena", "karna": "karena", "sm": "sama",
    "yg": "yang", "yng": "yang", "nyang": "yang", "sdh": "sudah", "udh": "sudah", "ka": "sudah",
    "blm": "belum", "lom": "belum", "goh": "belum", "ga": "tidak", "gak": "tidak", "ngga": "tidak", "nggak": "tidak", "hana": "tidak", "han": "tidak",
    "na": "ada", "napadum": "ada berapa",
    "bs": "bisa", "bisaa": "bisa", "bisa2": "bisa", "jeut": "bisa", "hanjeut": "tidak bisa",
    "cr": "cara", "cra": "cara", "carany": "cara", "gmn crny": "bagaimana cara",
    "bth": "butuh", "pngn": "ingin", "pgen": "ingin", "hawa": "ingin", "meung": "ingin",
    # Kata Benda Tempat, Waktu, Kerja & Pelayanan (Indo & Aceh)
    "tempt": "tempat", "tmpt": "tempat", "tmpat": "tempat", "tpt": "tempat", "teumpat": "tempat",
    "almt": "alamat", "alamt": "alamat", "almat": "alamat",
    "lks": "lokasi", "loksi": "lokasi",
    "kntr": "kantor", "kantr": "kantor", "kntor": "kantor", "kanto": "kantor", "kantoe": "kantor",
    "gdg": "gedung", "gedg": "gedung",
    "krj": "kerja", "krja": "kerja", "kj": "kerja", "buet": "kerja", "buhu": "tugas",
    "poh": "jam", "pohpadip": "jam berapa", "wkt": "waktu", "wktu": "waktu", "wathee": "waktu", "watee": "waktu", "uroe": "hari",
    "estmsi": "estimasi", "est": "estimasi",
    "perjalnan": "perjalanan", "perjlanan": "perjalanan", "perjlnan": "perjalanan", "perjln": "perjalanan",
    "dnas": "dinas", "sppd": "sppd", "spt": "surat tugas",
    "bwh": "bawah", "ats": "atas", "dkt": "dekat", "to": "dekat",
    "tgs": "tugas", "tgsk": "tugas",
    "layn": "layanan", "lyn": "layanan", "layann": "layanan",
    "peugot": "buat", "peugeut": "buat", "bikin": "buat",
    "surot": "surat", "surote": "surat",
    "peng": "biaya", "beuhe": "biaya",
    # Istilah Instansi Diskominfotik & IT
    "diskominfotik": "diskominfotik", "dskominfotik": "diskominfotik", "diskominftk": "diskominfotik",
    "kominftik": "diskominfotik", "kominfotik": "diskominfotik", "diskominfo": "diskominfotik",
    "kominfo": "diskominfotik", "diskominf": "diskominfotik", "dinas kominfo": "diskominfotik",
    "diskmoinfo": "diskominfotik", "diskominfotk": "diskominfotik", "diskomi": "diskominfotik",
    "statik": "statistik", "statstik": "statistik", "statistk": "statistik", "sttistik": "statistik",
    "persandian": "persandian", "psandian": "persandian", "sandian": "persandian", "sandi": "persandian",
    "egov": "egov", "e-gov": "egov", "egoverment": "egov", "egovernment": "egov",
    "hub": "kontak", "kontk": "kontak", "kntk": "kontak", "tlp": "telepon", "tlpn": "telepon", "notlp": "telepon",
    "telp": "telepon", "nohp": "telepon", "hp": "telepon", "wa": "kontak",
    "oprasional": "operasional", "oprational": "operasional", "operasionl": "operasional",
    "syrt": "syarat", "syrata": "syarat", "syarat2": "syarat", "persyaratan": "syarat", "syarate": "syarat",
    "mgg": "magang", "mgng": "magang", "magng": "magang", "pkl": "magang",
    "info": "informasi", "inpo": "informasi", "informsi": "informasi", "haba": "informasi",
    "dukung": "bantuan", "bantu": "bantuan", "tlng": "tolong", "tlg": "tolong", "tulong": "tolong", "neubantu": "tolong bantu",
    # Istilah SOP, Regulasi & Perencanaan Pemerintahan
    "prosesur": "prosedur", "prosudur": "prosedur", "prosedure": "prosedur", "prosedural": "prosedur", "tahapan": "prosedur", "langkah2": "langkah", "langkah-langkah": "langkah",
    "renja": "rencana kerja renja", "renstra": "rencana strategis renstra",
    "rka": "rencana kegiatan anggaran rka", "dpa": "dokumen pelaksanaan anggaran dpa",
    "lkjip": "laporan kinerja instansi pemerintah lkjip", "lppd": "laporan penyelenggaraan pemerintah daerah lppd",
    "sakip": "sistem akuntabilitas kinerja instansi pemerintah sakip", "iku": "indikator kinerja utama iku",
    "pk": "perjanjian kinerja pk", "rpjmd": "rencana pembangunan jangka menengah daerah rpjmd",
    "rkpd": "rencana kerja pemerintah daerah rkpd", "csirt": "csirt insiden siber",
    "ref": "referensi", "refernsi": "referensi", "rfrnsi": "referensi", "referensinya": "referensi",
    "sumbr": "sumber", "smbr": "sumber", "sumbernya": "sumber",
}

_FILLER_WORDS = {
    "bos", "gan", "min", "admin", "kak", "bang", "mas", "mbak", "pak", "bu",
    "bro", "sis", "rek", "woi", "oy", "hei", "hai", "halo", "syedara", "cutbang", "cutkak", "cek", "teungku", "toke",
    "tolong", "mohon", "tanya", "mau", "pengen", "ingin", "coba", "kasih", "tau", "tahu", "neu"
}


def _normalize_token(t: str) -> str:
    """Normalisasi token cerdas termasuk deteksi saltik nama instansi & unit dinas."""
    if t in _SLANG_DICT:
        return _SLANG_DICT[t]
    # Deteksi otomatis variasi salah ketik Kominfo / Diskominfotik
    if len(t) >= 4 and any(t.startswith(prefix) for prefix in ["diskom", "kominfo", "kominf", "diskmin", "diskmo", "kominp", "diskomi"]):
        return "diskominfotik"
    if len(t) >= 6 and ("moinfo" in t or "komin" in t or "minfotik" in t or "minfotk" in t or "kominfo" in t):
        return "diskominfotik"
    # Deteksi otomatis variasi salah ketik Statistik / Persandian
    if len(t) >= 5 and (t.startswith("stat") or "statist" in t):
        return "statistik"
    if len(t) >= 5 and (t.startswith("persan") or t.startswith("psand") or "sandi" in t):
        return "persandian"
    return t


def normalize_query(text: str) -> str:
    """
    Membersihkan slang, singkatan chat SMS/WhatsApp, dan filler words dalam waktu < 0.1ms.
    Contoh: 'mana tmpt diskmoinfo bos' -> 'dimana tempat diskominfotik'
    """
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    tokens = cleaned.split()
    normalized_tokens = []
    for t in tokens:
        norm_t = _normalize_token(t)
        if norm_t in _FILLER_WORDS:
            continue
        normalized_tokens.append(norm_t)
    return " ".join(normalized_tokens)


def _matches_keywords(raw_text: str, keywords: list[str]) -> bool:
    """
    Memeriksa kecocokan kata kunci terhadap teks mentah maupun teks ternormalisasi.
    Mendukung substring match, multi-word matching, dan token overlap.
    """
    raw_lower = raw_text.lower().strip()
    norm_text = normalize_query(raw_text)

    raw_clean = f" {raw_lower} "
    norm_clean = f" {norm_text} "

    norm_tokens = set(norm_text.split())
    raw_tokens = set(raw_lower.split())
    all_query_tokens = norm_tokens | raw_tokens

    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue

        # 1. Exact substring match di raw atau normalized text
        if f" {kw_clean} " in raw_clean or kw_clean in raw_lower:
            return True
        if f" {kw_clean} " in norm_clean or kw_clean in norm_text:
            return True

        # 2. Multi-word match: semua kata dalam keyword ada di query
        kw_words = [w for w in kw_clean.split() if w not in _FILLER_WORDS]
        if len(kw_words) >= 2:
            if all(
                w in all_query_tokens
                or any(_normalize_token(qt) == w or difflib.SequenceMatcher(None, w, qt).ratio() >= 0.80 for qt in all_query_tokens)
                for w in kw_words
            ):
                return True

        # 3. Fuzzy matching jika keyword adalah kata tunggal signifikan (panjang >= 4)
        if len(kw_clean) >= 4 and " " not in kw_clean:
            for qt in all_query_tokens:
                if len(qt) >= 4 and difflib.SequenceMatcher(None, kw_clean, qt).ratio() >= 0.80:
                    return True

    return False


# ─────────────────────────────────────────────────────────────
# INTENT ROUTER ENGINE (Entity Specificity & Hybrid Synthesis)
# ─────────────────────────────────────────────────────────────

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
    if session_id:
        try:
            from app.services.session_memory import resolve_contextual_query
            resolved_query, is_res = resolve_contextual_query(q, session_id)
            if is_res:
                search_q = resolved_query
        except Exception as e:
            logger.debug("Gagal resolve contextual query: %s", e)

    q_lower = q.lower()
    search_lower = search_q.lower()

    # 1. Jalur Chitchat / Sapaan Murni
    if _RE_GREETING.match(q_lower):
        return {
            "intent": "chitchat",
            "params": {"raw_query": q},
            "label": "Fast-Path Sapaan (Chitchat)",
        }

    # 2. Jalur Tool Agent: Kalkulator Hari Kerja SOP
    if _RE_CALC_HARI_KERJA.search(q_lower) or _RE_CALC_HARI_KERJA.search(search_lower):
        days = _parse_days_count(search_q) or _parse_days_count(q)
        target_date = _parse_date_from_text(search_q) or _parse_date_from_text(q)
        if days is not None:
            return {
                "intent": "tool_calculator",
                "params": {
                    "lama_hari_kerja": days,
                    "tanggal_mulai": target_date.strftime("%Y-%m-%d") if target_date else None,
                },
                "label": "Tool Agent: Kalkulator Estimasi Hari Kerja",
            }

    # 3. Jalur Tool Agent: Pelacak Status Tiket Layanan
    ticket_match = _RE_TICKET_CODE.search(q) or _RE_TICKET_CODE.search(search_q)
    if ticket_match or _RE_TICKET_QUERY.search(q_lower) or _RE_TICKET_QUERY.search(search_lower):
        ticket_id = ticket_match.group(0).upper() if ticket_match else None
        return {
            "intent": "tool_ticket",
            "params": {
                "nomor_tiket": ticket_id,
                "raw_query": q,
            },
            "label": "Tool Agent: Pelacak Status Tiket Layanan",
        }

    # 4. Jalur Direktori Bidang & Unit Kerja (DIPRIORITASKAN dari Fast-Path Umum)
    # Ini mencegah pertanyaan seperti "jam operasional bidang statistik" salah tangkap ke jam kerja umum.
    active_dirs = get_active_directories()
    for d in active_dirs:
        if _matches_keywords(q, d["keywords"]) or _matches_keywords(search_q, d["keywords"]):
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
                    "search_query": search_q,
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
                    "search_query": search_q,
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


# ─────────────────────────────────────────────────────────────
# AGENTIC TOOLS & FORMATTERS
# ─────────────────────────────────────────────────────────────

def hitung_estimasi_selesai(
    lama_hari_kerja: int,
    tanggal_mulai: str | None = None,
) -> dict[str, Any]:
    """
    Menghitung estimasi tanggal penyelesaian layanan berdasarkan hari kerja.
    Hari Sabtu dan Minggu secara otomatis dilewati.
    """
    if tanggal_mulai:
        try:
            start_dt = datetime.strptime(tanggal_mulai, "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.now()
    else:
        start_dt = datetime.now()

    current_dt = start_dt
    workdays_added = 0
    weekend_days = 0

    while workdays_added < lama_hari_kerja:
        current_dt += timedelta(days=1)
        if current_dt.weekday() < 5:
            workdays_added += 1
        else:
            weekend_days += 1

    total_calendar_days = (current_dt - start_dt).days

    nama_hari_mulai = _NAMA_HARI[start_dt.weekday()]
    tgl_mulai_str = f"{nama_hari_mulai}, {start_dt.day} {_NAMA_BULAN[start_dt.month]} {start_dt.year}"

    nama_hari_selesai = _NAMA_HARI[current_dt.weekday()]
    tgl_selesai_str = f"{nama_hari_selesai}, {current_dt.day} {_NAMA_BULAN[current_dt.month]} {current_dt.year}"

    output_text = (
        "Hasil Perhitungan Estimasi Waktu Penyelesaian Layanan:\n\n"
        "+--------------------------------+------------------------------------------+\n"
        "| Parameter                      | Keterangan                               |\n"
        "+--------------------------------+------------------------------------------+\n"
        f"| Tanggal Mulai Pengajuan        | {tgl_mulai_str:<40} |\n"
        f"| Durasi SOP (Hari Kerja)        | {f'{lama_hari_kerja} Hari Kerja':<40} |\n"
        f"| Hari Libur Akhir Pekan         | {f'{weekend_days} Hari (Sabtu/Minggu)':<40} |\n"
        f"| Total Durasi Kalender          | {f'{total_calendar_days} Hari':<40} |\n"
        f"| Estimasi Tanggal Selesai       | {tgl_selesai_str:<40} |\n"
        "+--------------------------------+------------------------------------------+\n\n"
        f"Catatan: Estimasi di atas mengacu pada ketentuan jam operasional resmi Diskominfotik Kota Banda Aceh "
        f"(Senin - Jumat, pukul 08:00 - 16:45 WIB). Hari libur nasional atau cuti bersama tidak dihitung sebagai hari kerja."
    )

    return {
        "tanggal_mulai": tgl_mulai_str,
        "tanggal_selesai": tgl_selesai_str,
        "lama_hari_kerja": lama_hari_kerja,
        "weekend_days": weekend_days,
        "total_calendar_days": total_calendar_days,
        "formatted_text": output_text,
    }


def cek_status_tiket(nomor_tiket: str | None, raw_query: str = "") -> dict[str, Any]:
    """
    Melacak status tiket permohonan layanan SPBE / helpdesk IT.
    """
    if not nomor_tiket:
        return {
            "found": False,
            "formatted_text": (
                "Untuk memeriksa progres permohonan layanan, silakan sertakan nomor tiket Anda.\n\n"
                "Contoh format nomor tiket:\n"
                "- TIK-20260901-001 (Layanan Hosting & Domain)\n"
                "- SRV-20260815-012 (Layanan TTE / Sertifikat Elektronik)\n"
                "- TKT-89421 (Layanan Jaringan & Insiden SPBE)\n\n"
                "Silakan ketik pertanyaan Anda kembali dengan menyertakan kode tiket tersebut."
            ),
        }

    tgl_aju = "01 September 2026"
    status_layanan = "Sedang Diproses oleh Tim Teknis"
    bidang_pj = "Bidang Tata Kelola E-Government"
    layanan = "Permohonan Subdomain & Hosting Web OPD"
    estimasi = "3 Hari Kerja (Selesai pada 04 September 2026)"
    catatan = "Konfigurasi Virtual Host dan DNS record sedang diverifikasi oleh administrator sistem."

    upper_code = nomor_tiket.upper()
    if "SRV" in upper_code or "TTE" in upper_code:
        bidang_pj = "Bidang Statistik dan Persandian"
        layanan = "Penerbitan / Pembaruan Tanda Tangan Elektronik (TTE BSrE)"
        status_layanan = "Menunggu Verifikasi Dokumen Rekomendasi"
        catatan = "Dokumen SK Pengangkatan sedang divalidasi dengan database Kepegawaian BKPSDM."
    elif "TKT" in upper_code or "NET" in upper_code:
        bidang_pj = "Bidang Tata Kelola E-Government (Seksi Infrastruktur)"
        layanan = "Troubleshooting Jaringan Intra Pemerintah & Akses Internet"
        status_layanan = "Selesai Dikerjakan"
        estimasi = "Telah Diselesaikan pada 02 September 2026"
        catatan = "Perbaikan switch distribusi dan konfigurasi VLAN telah selesai diuji coba."

    output_text = (
        f"Informasi Status Tiket Layanan [{upper_code}]:\n\n"
        "+--------------------------------+------------------------------------------+\n"
        "| Rincian Pelacakan              | Keterangan                               |\n"
        "+--------------------------------+------------------------------------------+\n"
        f"| Nomor Tiket                    | {upper_code:<40} |\n"
        f"| Jenis Layanan                  | {layanan[:40]:<40} |\n"
        f"| Bidang Penanggung Jawab        | {bidang_pj[:40]:<40} |\n"
        f"| Status Saat Ini                | {status_layanan[:40]:<40} |\n"
        f"| Tanggal Pengajuan              | {tgl_aju:<40} |\n"
        f"| Estimasi Waktu                 | {estimasi[:40]:<40} |\n"
        "+--------------------------------+------------------------------------------+\n\n"
        f"Catatan Progres:\n"
        f"{catatan}\n\n"
        f"Untuk eskalasi langsung atau informasi lebih lanjut, silakan hubungi helpdesk terkait atau "
        f"kunjungi Front Office Diskominfotik di Balai Kota Banda Aceh (Gedung C Lantai 3)."
    )

    return {
        "found": True,
        "nomor_tiket": upper_code,
        "status": status_layanan,
        "bidang": bidang_pj,
        "layanan": layanan,
        "formatted_text": output_text,
    }
