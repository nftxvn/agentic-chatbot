"""Parsing tanggal/durasi, pengayaan fakta, dan kalkulator hari kerja.

Kalkulator memakai aturan Senin-Jumat dan teks keluaran yang ada.
Hari libur nasional/cuti bersama belum dimodelkan dalam perhitungan.
"""

import calendar
import re
from datetime import datetime, timedelta
from typing import Any

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

