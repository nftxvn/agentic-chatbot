"""Normalisasi slang, filler, pencocokan keyword, dan penjaga kalimat tanya."""

import difflib
import re

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


_QUESTION_WORDS = {
    "siapa", "dimana", "di mana", "kemana", "ke mana", "kapan", "kenapa",
    "mengapa", "bagaimana", "gimana", "berapa", "apakah", "apa", "adakah",
    "bisakah", "bolehkah", "pat", "kiban", "pajan", "pakon", "padup", "padum",
    "so", "soe", "peue", "peu", "mana"
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


