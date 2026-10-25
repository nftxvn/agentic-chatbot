"""Ekstraksi nama warga, instansi, dan ringkasan kendala untuk handoff tiket."""

import re

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


