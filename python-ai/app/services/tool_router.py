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
import math
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

# Pola regex untuk rangkuman memori percakapan / session recap
_RE_SESSION_RECAP = re.compile(
    r"\b(bahas\s+apa|bicara\s+apa|ngomongin\s+apa|ngobrolin\s+apa|obrolan\s+kita|percakapan\s+kita|"
    r"tadi\s+(?:saya\s+)?tanya\s+apa|pertanyaan\s+saya\s+sebelumnya|rangkum\s+(?:obrolan|percakapan|topik)|"
    r"sebelumnya\s+kita\s+bahas|tadi\s+tentang\s+apa|kita\s+sedang\s+bahas\s+apa|topik\s+sebelumnya|"
    r"apa\s+yang\s+(?:tadi\s+)?kita\s+bahas|tadi\s+saya\s+bahas\s+apa|tadi\s+kita\s+ngapain)\b",
    re.IGNORECASE,
)

# Pola regex untuk obrolan santai, kabar, persona, identitas asisten
_RE_CHITCHAT_CONVERSATIONAL = re.compile(
    r"\b(apa\s+kabar|gimana\s+kabar|bagaimana\s+kabar|gimana\s+sehat|kamu\s+sehat|sehat\s+(?:kah|kan|ga|nggak)|kabare|kiban\s+haba|haba\s+kiban|peue\s+haba|peu\s+haba|"
    r"lagi\s+apa|lagi\s+ngapain|lagi\s+sibuk|kamu\s+lagi\s+apa|"
    r"kamu\s+siapa|anda\s+siapa|siapa\s+kamu|siapa\s+anda|siapa\s+namamu|nama\s+kamu\s+siapa|kamu\s+bisa\s+apa|bisa\s+bantu\s+apa|bisa\s+ngapain|kamu\s+robot|apakah\s+kamu\s+ai|siapa\s+pembuatmu|siapa\s+yang\s+buat\s+kamu|"
    r"terima\s+kasih|makasih|makasi|thanks|matur\s+nuwun|syukron|teurimong\s+gaseh|mantap|keren|good\s+job)\b",
    re.IGNORECASE,
)

# Pola regex untuk deteksi permintaan bantuan tim / operator manusia (Handover)
_RE_HUMAN_HANDOFF = re.compile(
    r"\b("
    r"(?:bicara|ngomong|ngobrol|diskusi|konsultasi|tanya|chat)\s+(?:langsung\s+)?(?:dengan|sama|ke|kepada)?\s*(?:pihak\s+)?(?:petugas|admin|manusia|staf|staff|operator|tim|orang|helpdesk|cs)|"
    r"(?:meng)?hubungi\s+(?:pihak\s+)?(?:petugas|admin|staf|staff|operator|manusia|tim|orang|helpdesk|cs)|"
    r"kontak\s+(?:pihak\s+)?(?:petugas|admin|staf|staff|operator|manusia|tim|orang|helpdesk|cs)|"
    r"(?:hubung(?:kan)?|sambung(?:kan)?|koneksi(?:kan)?|alih(?:kan)?|terhubung)\s+(?:(?:saya|kami|kita|tolong|dong|bisa|langsung)\s+)*(?:ke|dengan|sama|kepada)?\s*(?:pihak\s+)?(?:petugas|admin|operator|manusia|staf|staff|tim|orang|helpdesk|cs)|"
    r"(?:mau|ingin|butuh|perlu|minta|bisa|tolong|mohon)\s+(?:bantuan\s+(?:dari\s+)?)?(?:dibantu|bicara|ngomong|ngobrol|chat|tanya|konsultasi|terhubung|dihubungkan|disambungkan|dialihkan|menghubungi|kontak)?\s*(?:langsung\s+)?(?:dengan|sama|ke|kepada|dari)?\s*(?:pihak\s+)?(?:tim|admin|petugas|manusia|staf|staff|operator|orang|helpdesk|cs)|"
    r"panggil\s+(?:petugas|admin|operator|staf|staff|helpdesk)|"
    r"handover|takeover|live\s*agent|live\s*chat|human\s*agent|"
    r"(?:operator|petugas|admin|staf|staff|layanan)\s+(?:manusia|asli|manual)|"
    r"manusia\s+asli|orang\s+asli|staf\s+asli|"
    r"^(?:petugas|admin|operator|staf|staff|cs|helpdesk|live\s*agent)$|"
    r"^(?:iya|ya|mau|boleh|tolong)\s*(?:hubungi|sambungkan|hubungkan|alihkan|minta|ke|dengan|dong|bantu)?\s*(?:petugas|admin|operator|staf|staff|tim|orang|langsung)?"
    r")\b",
    re.IGNORECASE,
)

# Pola regex untuk sapaan dan uji coba (Termasuk Sapaan Bahasa Aceh & Santun)
_RE_GREETING = re.compile(
    r"^(?:(?:halo+|hai+|hay+|hei+|heyy+|hi+|hello+|helo+|hoi+|hoy+|oy+|oi+|woy+|woi+|uy+|yo+|assalamu['\s]?alaikum(?:\s+wr\s+wb|\s+warahmatullahi\s+wabarakatuh)?|ass|askum|"
    r"saleuem(?:\s+teuka)?|saleum(?:\s+teuka)?|kru\s+seumangat|kiban\s+haba|haba\s+kiban|peue\s+haba|peu\s+haba|"
    r"selamat\s+(?:pagi|siang|sore|malam)|pagi|siang|sore|malam|"
    r"tes|test|ping|p|testing|tes\s+123|test\s+123|"
    r"terima\s+kasih|makasih|thanks|matur\s+nuwun|syukron|teurimong\s+gaseh|"
    r"bot|asisten)"
    r"[\s,.-]*)+$",
    re.IGNORECASE,
)

# Pola regex untuk kalkulator estimasi waktu dan hari kerja
_RE_CALC_ESTIMASI_WAKTU = re.compile(
    r"\b(hitung\s+estimasi|estimasi\s+selesai|estimasi\s+waktu|berapa\s+hari\s+kerja|kapan\s+selesai|"
    r"hitung\s+hari\s+kerja|estimasi\s+tanggal|kalkulasi\s+hari\s+kerja|kalkulator\s+waktu|"
    r"lama\s+proses\s+\d+\s+hari|jika\s+(?:prosesnya\s+)?\d+\s+hari\s+kerja)\b",
    re.IGNORECASE,
)

# Pola regex untuk deteksi keraguan, sanggahan, atau koreksi jawaban sebelumnya
_RE_DOUBT_OR_CORRECTION = re.compile(
    r"\b(salah|keliru|bukan|bukannya|kok beda|kok salah|kok bisa|kenapa beda|memang iya|masa sih|yakin|beneran|serius|ngaco|bohong|ngibul|gak bener|tidak benar|kurang tepat|tidak tepat|hitung kembali|hitung ulang)\b",
    re.IGNORECASE,
)


def _is_doubt_or_correction_query(text: str) -> bool:
    """Mendeteksi apakah teks pengguna adalah bentuk keraguan, sanggahan, atau koreksi."""
    if not text:
        return False
    return bool(_RE_DOUBT_OR_CORRECTION.search(text))


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
    match = re.search(r"\b(\d+)\s*(?:hari\s*kerja|hari|uroe)\b", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Cek format angka hanya jika terdapat kata penanda waktu/durasi eksplisit
    match_fallback = re.search(r"(?:selama|dalam|waktu|durasi)\s+(\d+)\s*(?:hari|uroe)?\b", text, re.IGNORECASE)
    if match_fallback and any(w in text.lower() for w in ["hari", "uroe", "kerja"]):
        try:
            val = int(match_fallback.group(1))
            if 1 <= val <= 365:
                return val
        except ValueError:
            pass

    return None


def parse_and_sum_durations_from_context(context_text: str) -> dict[str, Any] | None:
    """
    Kalkulator Masa Tempuh & Durasi Waktu:
    Mengekstrak seluruh rincian waktu (menit, jam, hari) dari teks langkah/SOP
    dan menghitung total akumulasi durasinya secara presisi matematis.
    """
    if not context_text:
        return None

    total_menit = 0.0
    total_hari = 0.0
    items = []

    lines = context_text.split('\n')
    for line in lines:
        # Cari baris yang mengandung penanda waktu (Waktu:, Durasi:)
        match = re.search(r"(?:waktu|durasi|lama)\s*[:=]\s*(.+)", line, re.IGNORECASE)
        if match:
            time_str = match.group(1).strip()
            # Ekstrak semua angka + satuan di baris ini
            sub_matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(menit|jam|hari|detik)", time_str, re.IGNORECASE)
            
            if not sub_matches:
                continue
            
            max_val_in_minutes = 0.0
            best_unit_str = ""
            best_hari_val = 0.0
            
            for val_str, unit in sub_matches:
                val = float(val_str.replace(",", "."))
                u = unit.lower()
                
                val_in_minutes = 0.0
                hari_val = 0.0
                
                if "hari" in u:
                    val_in_minutes = val * 24 * 60
                    hari_val = val
                elif "jam" in u:
                    val_in_minutes = val * 60
                elif "menit" in u:
                    val_in_minutes = val
                elif "detik" in u:
                    val_in_minutes = val / 60
                    
                # Gunakan max-pooling (ambil durasi terlama dalam rentang)
                if val_in_minutes > max_val_in_minutes:
                    max_val_in_minutes = val_in_minutes
                    best_unit_str = f"{int(val) if val.is_integer() else val} {u}"
                    if "kerja" in time_str.lower() and "hari" in u:
                        best_unit_str += " kerja"
                    best_hari_val = hari_val
                    
            if max_val_in_minutes > 0:
                if best_hari_val > 0:
                    total_hari += best_hari_val
                else:
                    total_menit += max_val_in_minutes
                items.append(best_unit_str)

    # Fallback: Jika sama sekali tidak ada kata "Waktu:" atau "Durasi:"
    if not items:
        time_matches = re.findall(
            r"\b(\d+(?:[.,]\d+)?)\s*(menit|jam|hari|detik)\b",
            context_text,
            re.IGNORECASE,
        )
        if not time_matches or len(time_matches) < 2:
            return None
            
        for val_str, unit in time_matches:
            val = float(val_str.replace(",", "."))
            u = unit.lower().strip()
            if "menit" in u:
                total_menit += val
                items.append(f"{int(val) if val.is_integer() else val} menit")
            elif "jam" in u:
                total_menit += val * 60
                items.append(f"{int(val) if val.is_integer() else val} jam")
            elif "hari" in u:
                total_hari += val
                items.append(f"{int(val) if val.is_integer() else val} hari")
            elif "detik" in u:
                total_menit += val / 60
                items.append(f"{int(val) if val.is_integer() else val} detik")

    if not items:
        return None

    # Normalisasi sisa waktu jika melebihi 24 jam
    if total_menit > 0:
        jam_t = int(total_menit // 60)
        if jam_t >= 24:
            tambahan_hari = jam_t // 24
            total_hari += tambahan_hari
            total_menit = total_menit - (tambahan_hari * 24 * 60)

    hari_str = f"{int(total_hari) if total_hari.is_integer() else total_hari} hari" if total_hari > 0 else ""

    if total_menit > 0:
        jam = int(total_menit // 60)
        sisa_menit = int(total_menit % 60)
        if jam > 0 and sisa_menit > 0:
            time_part = f"{jam} jam {sisa_menit} menit"
        elif jam > 0:
            time_part = f"{jam} jam"
        else:
            time_part = f"{int(total_menit)} menit"
    else:
        time_part = ""

    if total_hari > 0 and time_part:
        formatted_total = f"{hari_str} dan {time_part}"
    elif total_hari > 0:
        formatted_total = f"{hari_str}"
    elif time_part:
        formatted_total = f"{time_part}"
    else:
        formatted_total = "0 menit"

    return {
        "items": items,
        "total_menit": total_menit,
        "total_hari": total_hari,
        "formatted_total": formatted_total,
    }


import calendar


def _calculate_calendar_difference(d1: datetime, d2: datetime) -> tuple[int, int, int]:
    """
    Menghitung selisih kalender gregorian presisi (years, months, days)
    antara dua objek datetime (d1 <= d2).
    """
    if d1 > d2:
        d1, d2 = d2, d1

    try:
        from dateutil.relativedelta import relativedelta
        rd = relativedelta(d2, d1)
        return rd.years, rd.months, rd.days
    except Exception:
        pass

    # Algoritma Kalender Gregorian Murni (Fallback Standar)
    years = d2.year - d1.year
    months = d2.month - d1.month
    days = d2.day - d1.day

    if days < 0:
        months -= 1
        prev_month = d2.month - 1 if d2.month > 1 else 12
        prev_year = d2.year if d2.month > 1 else d2.year - 1
        _, max_days_prev = calendar.monthrange(prev_year, prev_month)
        days += max_days_prev

    if months < 0:
        years -= 1
        months += 12

    return years, months, days


def _format_human_duration(years: int, months: int, days: int) -> str:
    """Format durasi tahun, bulan, hari yang natural."""
    parts = []
    if years > 0:
        parts.append(f"{years} tahun")
    if months > 0:
        parts.append(f"{months} bulan")
    if days > 0:
        parts.append(f"{days} hari")
    return " ".join(parts) if parts else "0 hari"


def _enrich_facts_with_date_calculations(facts_text: str) -> str:
    """
    Kalkulator Masa Durasi Waktu (Best Practice Kalender Riil):
    Mendeteksi tanggal di dalam fakta resmi dan menghitung selisih masa waktu
    secara presisi kalender (hari, bulan, tahun) hingga hari ini atau hitung mundur.
    """
    now = datetime.now()
    parsed_date = _parse_date_from_text(facts_text)
    if not parsed_date:
        return facts_text

    diff = now - parsed_date
    total_days = diff.days

    hari_ini_str = f"{_NAMA_HARI[now.weekday()]}, {now.day} {_NAMA_BULAN[now.month]} {now.year}"
    tgl_peristiwa_str = f"{parsed_date.day} {_NAMA_BULAN[parsed_date.month]} {parsed_date.year}"

    if total_days >= 0:
        years, months, days = _calculate_calendar_difference(parsed_date, now)
        human_dur = _format_human_duration(years, months, days)
        combined_dur = f"{human_dur} (total {total_days} hari)" if human_dur != f"{total_days} hari" else f"{total_days} hari"

        calc_note = (
            f"\n- Data Perhitungan Masa Durasi Waktu (Hingga Hari Ini: {hari_ini_str}):\n"
            f"  * Terhitung sejak tanggal {tgl_peristiwa_str} sampai hari ini ({hari_ini_str}), "
            f"masa waktu yang telah berjalan adalah TEPAT {combined_dur}.\n"
            f"  * Jika pengguna menanyakan masa waktu, lama berlangsung, atau durasi jabatan/kerja, "
            f"rujuk hasil perhitungan kalender riil ini: {combined_dur}."
        )
    else:
        future_days = abs(total_days)
        years, months, days = _calculate_calendar_difference(now, parsed_date)
        human_dur = _format_human_duration(years, months, days)
        combined_dur = f"{human_dur} (total {future_days} hari lagi)" if human_dur != f"{future_days} hari" else f"{future_days} hari lagi"

        calc_note = (
            f"\n- Data Perhitungan Estimasi Waktu ke Depan (Dari Hari Ini: {hari_ini_str}):\n"
            f"  * Tanggal {tgl_peristiwa_str} adalah {future_days} hari lagi dari hari ini ({human_dur} ke depan).\n"
            f"  * Rujuk estimasi waktu ini bila pengguna menanyakan sisa waktu atau hitung mundur: {combined_dur}."
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
    "ap": "apa", "apkh": "apakah", "apaan": "apa", "peue": "apa", "peu": "apa", "peuh": "apa", "aj": "saja", "aja": "saja", "aje": "saja",
    "so": "siapa", "soe": "siapa",
    "sy": "saya", "aq": "saya", "gw": "saya", "gue": "saya", "ane": "saya", "lon": "saya", "ulon": "saya",
    "km": "kamu", "lu": "anda", "lo": "anda", "dron": "anda", "droeneuh": "anda", "gata": "kamu",
    "dr": "dari", "dlm": "dalam", "lam": "dalam", "utk": "untuk", "untk": "untuk", "keu": "untuk", "keupeu": "untuk apa",
    "dgn": "dengan", "dg": "dengan", "ngon": "dengan", "krn": "karena", "karna": "karena", "sm": "sama",
    "yg": "yang", "yng": "yang", "nyang": "yang", "sdh": "sudah", "udh": "sudah", "ka": "sudah",
    "blm": "belum", "lom": "belum", "goh": "belum", "ga": "tidak", "gak": "tidak", "ngga": "tidak", "nggak": "tidak", "hana": "tidak", "han": "tidak",
    "na": "ada", "napadum": "ada berapa",
    "bs": "bisa", "bisaa": "bisa", "bisa2": "bisa", "jeut": "bisa", "hanjeut": "tidak bisa",
    "cr": "cara", "cra": "cara", "carany": "cara", "caranya": "cara", "crny": "cara", "gmn crny": "bagaimana cara",
    "bth": "butuh", "pngn": "ingin", "pgen": "ingin", "hawa": "ingin", "meung": "ingin",
    "kalw": "kalau", "klo": "kalau", "klw": "kalau", "kl": "kalau", "kalo": "kalau", "kalu": "kalau",
    "smw": "semua", "semuany": "semua", "semuanya": "semua", "smua": "semua",
    "lngkp": "lengkap", "lengkp": "lengkap", "lengkapny": "lengkap", "lengkapnya": "lengkap",
    "siapny": "selesai", "siapnya": "selesai", "kelar": "selesai", "kelarny": "selesai",
    "tny": "tanya", "tnya": "tanya", "ttg": "tentang", "tentg": "tentang",
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
    "peugot": "buat", "peugeut": "buat", "bikin": "buat", "bkin": "buat",
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
    "syrt": "syarat", "syrata": "syarat", "syarat2": "syarat", "syrt2": "syarat", "syrtny": "syarat", "syaratny": "syarat", "syaratnya": "syarat", "persyaratan": "syarat", "syarate": "syarat",
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
    "bos", "gan", "min", "kak", "bang", "mas", "mbak", "pak", "bu",
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
    Mendukung exact word boundary match, multi-word sequential phrase matching, dan token matching.
    """
    if not raw_text or not keywords:
        return False

    raw_lower = raw_text.lower().strip()
    norm_text = normalize_query(raw_text)

    norm_tokens = set(norm_text.split())
    raw_tokens = set(raw_lower.split())
    all_query_tokens = norm_tokens | raw_tokens

    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue

        # 1. Exact phrase match dengan word boundaries di raw atau normalized text
        pattern = rf"\b{re.escape(kw_clean)}\b"
        if re.search(pattern, raw_lower) or re.search(pattern, norm_text):
            return True

        kw_words = [w for w in kw_clean.split() if w not in _FILLER_WORDS]
        if not kw_words:
            continue

        # 2. Multi-word phrase: kata-kata harus berurutan dengan jeda maksimal 2 kata penghubung/filler
        if len(kw_words) >= 2:
            phrase_pattern = r"\b" + r"\s+(?:\w+\s+){0,2}".join(re.escape(w) for w in kw_words) + r"\b"
            if re.search(phrase_pattern, raw_lower) or re.search(phrase_pattern, norm_text):
                return True
        elif len(kw_words) == 1:
            w = kw_words[0]
            # Exact token match
            if w in all_query_tokens:
                return True
            # Fuzzy match hanya jika kata kunci entitas cukup panjang (>= 5 huruf)
            if len(w) >= 5:
                for qt in all_query_tokens:
                    if len(qt) >= 5 and difflib.SequenceMatcher(None, w, qt).ratio() >= 0.85:
                        return True

    return False


# ─────────────────────────────────────────────────────────────
# AI-NATIVE SEMANTIC INTENT CLASSIFIER (Cosine Similarity)
# ─────────────────────────────────────────────────────────────

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


_NAME_STOPWORDS = {
    "mau", "ingin", "butuh", "perlu", "ada", "hendak", "belum", "tidak", "tak", "bukan",
    "sedang", "baru", "sudah", "telah", "minta", "mohon", "bertanya", "tanya", "bingung",
    "rasa", "kira", "cuma", "hanya", "kan", "ini", "itu", "warga", "masyarakat", "umum",
    "seorang", "seseorang", "orang", "admin", "petugas", "operator", "cs", "helpdesk", "pihak", "siapa",
    "manusia", "staf", "staff", "tim", "bantuan", "cara", "cepat", "mudah", "baik", "bisa",
    "boleh", "dapat", "tolong", "dong", "halo", "hai", "selamat", "pagi", "siang", "sore",
    "malam", "assalamualaikum", "waalaikumsalam", "terima", "kasih", "makasih", "bapak",
    "ibu", "pak", "bu", "mas", "mbak", "hormat", "info", "informasi", "kendala", "masalah",
    "keluhan", "keperluan", "perihal", "kebutuhan", "dari", "kantor", "instansi", "opd",
    "dinas", "badan", "bagian", "bidang", "kementerian", "lembaga", "kecamatan", "puskesmas",
    "di", "ke", "pada", "untuk", "atas", "nama", "dengan", "sama", "saya", "kami", "kita",
    "adalah", "yaitu", "dan", "serta", "yg", "yang", "juga", "atau", "pun", "karena", "sebab",
    "bicara", "berbicara", "ngobrol", "ngomong", "diskusi", "konsultasi", "konsul", "chat",
    "chatting", "hubung", "hubungi", "menghubungi", "dihubungi", "sambung", "sambungkan",
    "hubungkan", "alih", "alihkan", "kontak", "mengontak", "pesan", "kirim", "bertemu",
    "ketemu", "panggil", "langsung",
    "mahasiswa", "mahasiswi", "dosen", "guru", "honorer", "asn", "pns", "pppk", "siswa",
    "siswi", "pelajar", "alumni", "rekan", "anggota", "kepala", "ketua", "sekretaris",
    "bendahara", "kabid", "kasi", "kadis", "direktur", "dekan", "rektor",
    "dimana", "di mana", "mana", "alamat", "lokasi", "tempat", "gedung", "kapan", "mengapa",
    "kenapa", "bagaimana", "gimana", "berapa", "apakah", "apa", "adakah", "sekarang", "saat",
    "hari", "ini", "itu",
}

_INVALID_AGENCY_TERMS = {
    "sekarang", "saat ini", "ini", "itu", "terkait", "tersebut", "setempat",
    "baru", "lama", "mana", "dimana", "apa", "siapa", "tanya", "tau", "tahu",
    "aja", "saja", "nya", "kantor", "dinas", "badan", "opd", "instansi",
    "bagian", "bidang", "puskesmas", "kecamatan", "kementerian", "rsud", "unit kerja"
}

_QUESTION_WORDS = {
    "siapa", "dimana", "di mana", "kemana", "ke mana", "kapan", "kenapa",
    "mengapa", "bagaimana", "gimana", "berapa", "apakah", "apa", "adakah",
    "bisakah", "bolehkah", "pat", "kiban", "pajan", "pakon", "padup", "padum",
    "so", "soe", "peue", "peu", "mana"
}


def _is_interrogative_query(text: str) -> bool:
    """Mendeteksi apakah query adalah kalimat tanya (bukan pengisian data bantuan / intro)."""
    if not text:
        return False
    t = text.lower().strip()
    if "?" in t:
        return True
    cleaned = re.sub(r"[^\w\s]", " ", t)
    tokens = cleaned.split()
    if not tokens:
        return False
    # Kata tanya di awal kalimat
    if tokens[0] in _QUESTION_WORDS:
        return True
    if len(tokens) >= 2 and f"{tokens[0]} {tokens[1]}" in _QUESTION_WORDS:
        return True
    # Kata tanya di dalam kalimat (misal: "tolong jelaskan siapa kepala dinas")
    for q_kw in ["siapa", "dimana", "di mana", "kapan", "mengapa", "kenapa", "bagaimana", "gimana", "berapa", "apakah"]:
        if re.search(rf"\b{re.escape(q_kw)}\b", t):
            if not re.search(r"\b(?:nama|instansi|opd|kendala|masalah|keluhan)\s*[:=]", t):
                return True
    return False

_AGENCY_ALIASES = {
    "kemenkes": "Kementerian Kesehatan",
    "kemkes": "Kementerian Kesehatan",
    "kemendikbud": "Kementerian Pendidikan dan Kebudayaan",
    "kemedikbud": "Kementerian Pendidikan dan Kebudayaan",
    "kemdikbud": "Kementerian Pendidikan dan Kebudayaan",
    "kemendikbudristek": "Kementerian Pendidikan dan Kebudayaan",
    "kemendiknas": "Kementerian Pendidikan dan Kebudayaan",
    "kemenag": "Kementerian Agama",
    "kemag": "Kementerian Agama",
    "kemendagri": "Kementerian Dalam Negeri",
    "kemendag": "Kementerian Perdagangan",
    "kemenkeu": "Kementerian Keuangan",
    "kemenkumham": "Kemenkumham",
    "kemenko": "Kementerian Koordinator",
    "kemenhub": "Kementerian Perhubungan",
    "kemenpan": "KemenPAN-RB",
    "kemenpanrb": "KemenPAN-RB",
    "kemkominfo": "Kementerian Komunikasi dan Digital",
    "komdigi": "Kementerian Komunikasi dan Digital",
    "diskominfo": "Diskominfotik",
    "diskominfotik": "Diskominfotik",
    "kominfo": "Diskominfotik",
    "bappeda": "Bappeda",
    "bkpsdm": "BKPSDM",
    "bpkk": "BPKK",
    "bpbd": "BPBD",
    "dinkes": "Dinas Kesehatan",
    "diskes": "Dinas Kesehatan",
    "disdik": "Dinas Pendidikan dan Kebudayaan",
    "disdikbud": "Dinas Pendidikan dan Kebudayaan",
    "disdukcapil": "Disdukcapil",
    "dukcapil": "Disdukcapil",
    "dishub": "Dinas Perhubungan",
    "dinsos": "Dinas Sosial",
    "pupr": "Dinas PUPR",
    "dlhk": "DLHK3",
    "dlhk3": "DLHK3",
    "dpmptsp": "DPMPTSP",
    "inspektorat": "Inspektorat",
    "setda": "Setda Kota Banda Aceh",
    "setdako": "Setdako Banda Aceh",
    "satpol": "Satpol PP & WH",
    "satpolpp": "Satpol PP & WH",
    "satpol pp": "Satpol PP & WH",
    "uin": "UIN Ar-Raniry",
    "uin ar raniry": "UIN Ar-Raniry",
    "uin ar-raniry": "UIN Ar-Raniry",
    "ar raniry": "UIN Ar-Raniry",
    "ar-raniry": "UIN Ar-Raniry",
    "usk": "Universitas Syiah Kuala",
    "unsyiah": "Universitas Syiah Kuala",
    "unida": "Universitas Iskandar Muda",
    "ummuha": "Universitas Muhammadiyah Aceh",
    "poltekkes": "Poltekkes Kemenkes Aceh",
    "bbpmp": "BBPMP Aceh",
    "lan": "Puslatbang KHAN LAN RI",
}


def _clean_extracted_name(raw: str | None) -> str | None:
    if not raw:
        return None
    trimmed = raw.strip(" \t\n\r.,:;!?-/|")
    cleaned = re.sub(r"[^A-Za-z\s'\.]", "", trimmed).strip()
    words = cleaned.split()
    if not words:
        return None

    valid_words = []
    for w in words:
        if w.lower() in _NAME_STOPWORDS:
            if valid_words:
                break
            continue
        valid_words.append(w)

    if not valid_words:
        return None

    if len(valid_words) > 4:
        valid_words = valid_words[:4]

    final_name = " ".join(valid_words).title()
    return final_name if len(final_name) >= 2 else None


def _clean_extracted_agency(raw: str | None) -> str | None:
    if not raw:
        return None
    raw_trim = raw.strip(" \t\n\r.,:;!?-/|")
    lower = raw_trim.lower()
    if not re.match(r"^(?:dinas|badan|bagian|bidang|kementerian|kecamatan|puskesmas|rsud|setda|inspektorat)\b", lower, flags=re.IGNORECASE):
        lower = re.sub(r"^(?:dari|staf\s+di|staf|pegawai\s+di|pegawai|mahasiswa\s+di|mahasiswa|mahasiswi\s+di|mahasiswi|dosen\s+di|dosen|guru|alumni|kantor|opd|instansi|asal)\s+", "", lower).strip(" \t\n\r.,:;!?-/|")

    # Tolak jika nama instansi hanya berupa kata umum/keterangan waktu
    if lower in _INVALID_AGENCY_TERMS:
        return None

    # Hapus imbuhan dinas/badan untuk mengecek apakah kata intinya valid
    stripped_core = re.sub(r"^(?:dinas|badan|bagian|bidang|kementerian|kecamatan|puskesmas|rsud|setda|inspektorat)\s*", "", lower).strip()
    if not stripped_core or stripped_core in _INVALID_AGENCY_TERMS:
        return None

    sorted_aliases = sorted(_AGENCY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for alias, canonical in sorted_aliases:
        if lower == alias or lower.startswith(alias + " ") or lower.startswith(alias + ","):
            suffix = lower[len(alias):].strip(" ,-")
            if not suffix or suffix in canonical.lower() or suffix in _INVALID_AGENCY_TERMS:
                return canonical
            return f"{canonical} {suffix.title()}".strip()

    res = lower.title()
    for acr in ["OPD", "SPPD", "SOP", "BKPSDM", "Bappeda", "BPKK", "BPBD", "RSUD", "UPTD", "DLHK3", "Disdukcapil", "DPMPTSP"]:
        res = re.sub(rf"\b{acr}\b", acr, res, flags=re.IGNORECASE)
    return res if len(res) >= 2 else None


def extract_citizen_escalation_details(text: str) -> dict[str, str | None]:
    """Mengekstrak informasi Nama, Instansi, dan Kendala dari pesan tindak lanjut warga."""
    details = {"citizen_name": None, "citizen_agency": None, "issue_summary": None}
    
    # Bersihkan simbol markdown bullets dan bolding agar parsing key-value tahan terhadap copy-paste template
    clean_txt = re.sub(r"[*_•\-]+", " ", text)

    # Pola lookahead pembatas agar tidak merebut kunci berikutnya dalam 1 baris
    next_key_pat = r"(?=\s+(?:nama|instansi|opd|unit\s+kerja|kantor|asal|kendala|masalah|keluhan|keperluan|perihal|kebutuhan|hp|wa|telepon|kontak|telp|no)\s*[:=]|$|\n|\,|\/|\|)"

    # 1. Format Terstruktur Key-Value (e.g. Nama: Budi, Nama saya: Budi, Instansi: Dinkes, Instansi/OPD: Kemenkes)
    m_name_kv = re.search(r"(?:nama(?:\s*(?:saya|ku))?|name)\s*[:=]\s*([^,\/\n\|\.]+?)" + next_key_pat, clean_txt, re.IGNORECASE)
    if m_name_kv:
        cand = _clean_extracted_name(m_name_kv.group(1))
        if cand:
            details["citizen_name"] = cand

    m_agency_kv = re.search(r"(?:instansi(?:\s*\/\s*opd)?|opd|unit\s+kerja|kantor|asal)\s*[:=]\s*([^,\/\n\|\.]+?)" + next_key_pat, clean_txt, re.IGNORECASE)
    if m_agency_kv:
        cand = _clean_extracted_agency(m_agency_kv.group(1))
        if cand:
            details["citizen_agency"] = cand

    m_issue_kv = re.search(r"(?:kendala|masalah|keluhan|keperluan|perihal|kebutuhan)\s*[:=]\s*(.+?)" + next_key_pat, clean_txt, re.IGNORECASE | re.DOTALL)
    if m_issue_kv:
        raw_issue = m_issue_kv.group(1).strip()
        raw_issue = re.sub(r"^(?:saya|kami|adalah|yaitu)?\s*[:=]?\s*", "", raw_issue, flags=re.IGNORECASE)
        details["issue_summary"] = raw_issue.strip()

    # 2. Pola Alami Bahasa Indonesia untuk Nama
    if not details["citizen_name"]:
        name_patterns = [
            r"(?:nama\s*(?:saya|ku)?|namaku|atas\s+nama|panggil\s+saja)\s*(?:adalah|:|=)?\s*([A-Za-z\s'\.]{2,35}?)(?=\s+(?:dari|staf|pegawai|mahasiswa|mahasiswi|dosen|guru|honorer|asn|pns|pppk|siswa|siswi|pelajar|alumni|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|kendala|masalah|keperluan|ingin|mau|tolong|dan|serta|\.|\,|\n|$))",
            r"(?:perkenalkan\s+(?:nama\s+)?saya|perkenalkan)\s+([A-Za-z\s'\.]{2,30}?)(?=\s+(?:dari|staf|pegawai|mahasiswa|mahasiswi|dosen|guru|honorer|asn|pns|pppk|siswa|siswi|pelajar|alumni|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|kendala|masalah|keperluan|ingin|mau|tolong|dan|serta|\.|\,|\n|$))",
            r"(?:saya|dengan|aku)\s+([A-Za-z\s'\.]{2,30}?)\s+(?:dari|staf\s+(?:di|pada|ke)?|pegawai\s+(?:di|pada|ke)?|mahasiswa\s+(?:di|pada|ke)?|mahasiswi\s+(?:di|pada|ke)?|dosen\s+(?:di|pada|ke)?|guru\s+(?:di|pada|ke)?|kantor|opd|instansi|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas)\b",
            r"^([A-Za-z\s'\.]{2,30}?)\s+(?:dari|instansi|asal|kantor|staf|pegawai|mahasiswa|mahasiswi|dosen|guru)\s+",
        ]
        for pat in name_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                cand = _clean_extracted_name(m.group(1))
                if cand:
                    details["citizen_name"] = cand
                    break

    # 3. Pola Alami Bahasa Indonesia untuk Instansi
    if not details["citizen_agency"]:
        agency_patterns = [
            r"(?:dari|staf\s+(?:di|pada|ke)?|pegawai\s+(?:di|pada|ke)?|mahasiswa\s+(?:di|pada|ke)?|mahasiswi\s+(?:di|pada|ke)?|dosen\s+(?:di|pada|ke)?|guru\s+(?:di|pada|ke)?|alumni\s+(?:dari)?|kantor|bagian|bidang|opd|instansi|asal)\s*[:=]?\s*([A-Za-z0-9\s'\.\-_]{2,50}?)(?=\s+(?:mau|ingin|butuh|perlu|tolong|mohon|kendala|masalah|keluhan|keperluan|\.|\,|\n|$))",
            r"\b(dinas\s+[a-z0-9\s\.\-_]+|badan\s+[a-z0-9\s\.\-_]+|kementerian\s+[a-z0-9\s\.\-_]+|universitas\s+[a-z0-9\s\.\-_]+|kampus\s+[a-z0-9\s\.\-_]+|inspektorat(?:\s+[a-z0-9\s\.\-_]+)?|setda(?:ko)?(?:\s+[a-z0-9\s\.\-_]+)?|sekretariat\s+daerah(?:\s+[a-z0-9\s\.\-_]+)?|satpol\s*pp(?:\s*&\s*wh)?|kecamatan\s+[a-z0-9\s\.\-_]+|camat\s+[a-z0-9\s\.\-_]+|puskesmas\s+[a-z0-9\s\.\-_]+|rsud\s+[a-z0-9\s\.\-_]+|bagian\s+[a-z0-9\s\.\-_]+|bidang\s+[a-z0-9\s\.\-_]+)\b",
            r"\b(kemenkes|kemkes|kemendikbud|kemedikbud|kemdikbud|kemendikbudristek|kemenag|kemendagri|kemendag|kemenkeu|kemenkumham|kemenko|kemenhub|kemenpan|kemenpanrb|kemkominfo|komdigi|bappeda|bkpsdm|bpkk|bpbd|diskominfo[a-z]*|dinkes|diskes|disdikbud|disdik|dishub|dinsos|pupr|dlhk3?|dpmptsp|uin(?:\s+ar[\s\-]raniry)?|usk|unsyiah|unida|ummuha|poltekkes)(?:\s+[a-z0-9\s\.\-_]+)?\b",
        ]
        for pat in agency_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                cand = _clean_extracted_agency(m.group(1))
                if cand:
                    details["citizen_agency"] = cand
                    break

    # 4. Ringkasan Kendala
    if not details["issue_summary"]:
        m_nat_issue = re.search(r"(?:kendala|masalah|keluhan|keperluan|perihal)\s*(?:saya|kami)?\s*[:=]?\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        if m_nat_issue:
            raw_issue = m_nat_issue.group(1).strip()
            raw_issue = re.sub(r"^(?:saya|kami|adalah|yaitu)?\s*[:=]?\s*", "", raw_issue, flags=re.IGNORECASE)
            details["issue_summary"] = raw_issue.strip()
        else:
            details["issue_summary"] = text.strip()

    return details


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


# ─────────────────────────────────────────────────────────────
# AGENTIC TOOLS & FORMATTERS
# ─────────────────────────────────────────────────────────────

def hitung_estimasi_selesai(
    lama_hari_kerja: int,
    tanggal_mulai: str | None = None,
) -> dict[str, Any]:
    """
    Kalkulator Estimasi Waktu & Target Selesai:
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
        "Hasil Perhitungan Estimasi Waktu Penyelesaian:\n\n"
        "+--------------------------------+------------------------------------------+\n"
        "| Parameter                      | Keterangan                               |\n"
        "+--------------------------------+------------------------------------------+\n"
        f"| Tanggal Mulai                  | {tgl_mulai_str:<40} |\n"
        f"| Durasi (Hari Kerja)            | {f'{lama_hari_kerja} Hari Kerja':<40} |\n"
        f"| Hari Libur Akhir Pekan         | {f'{weekend_days} Hari (Sabtu/Minggu)':<40} |\n"
        f"| Total Durasi Kalender          | {f'{total_calendar_days} Hari':<40} |\n"
        f"| Estimasi Tanggal Selesai       | {tgl_selesai_str:<40} |\n"
        "+--------------------------------+------------------------------------------+\n\n"
        f"Catatan: Perhitungan mengacu pada hari kerja aktif (Senin - Jumat). "
        f"Hari libur nasional atau cuti bersama tidak dihitung sebagai hari kerja."
    )

    return {
        "tanggal_mulai": tgl_mulai_str,
        "tanggal_selesai": tgl_selesai_str,
        "lama_hari_kerja": lama_hari_kerja,
        "weekend_days": weekend_days,
        "total_calendar_days": total_calendar_days,
        "formatted_text": output_text,
    }
