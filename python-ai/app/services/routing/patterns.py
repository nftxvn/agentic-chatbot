"""Pola intent untuk rangkuman, sapaan, eskalasi, koreksi, dan kalkulator."""

import re

_RE_SESSION_RECAP = re.compile(
    r"\b(bahas\s+apa|bicara\s+apa|ngomongin\s+apa|ngobrolin\s+apa|obrolan\s+kita|percakapan\s+kita|"
    r"tadi\s+(?:saya\s+)?tanya\s+apa|pertanyaan\s+saya\s+sebelumnya|rangkum\s+(?:obrolan|percakapan|topik)|"
    r"sebelumnya\s+kita\s+bahas|tadi\s+tentang\s+apa|kita\s+sedang\s+bahas\s+apa|topik\s+sebelumnya|"
    r"apa\s+yang\s+(?:tadi\s+)?kita\s+bahas|tadi\s+saya\s+bahas\s+apa|tadi\s+kita\s+ngapain)\b",
    re.IGNORECASE,
)


_RE_CHITCHAT_CONVERSATIONAL = re.compile(
    r"\b(apa\s+kabar|gimana\s+kabar|bagaimana\s+kabar|gimana\s+sehat|kamu\s+sehat|sehat\s+(?:kah|kan|ga|nggak)|kabare|kiban\s+haba|haba\s+kiban|peue\s+haba|peu\s+haba|"
    r"lagi\s+apa|lagi\s+ngapain|lagi\s+sibuk|kamu\s+lagi\s+apa|"
    r"kamu\s+siapa|anda\s+siapa|siapa\s+kamu|siapa\s+anda|siapa\s+namamu|nama\s+kamu\s+siapa|kamu\s+bisa\s+apa|bisa\s+bantu\s+apa|bisa\s+ngapain|kamu\s+robot|apakah\s+kamu\s+ai|siapa\s+pembuatmu|siapa\s+yang\s+buat\s+kamu|"
    r"terima\s+kasih|makasih|makasi|thanks|matur\s+nuwun|syukron|teurimong\s+gaseh|mantap|keren|good\s+job)\b",
    re.IGNORECASE,
)


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


_RE_CALC_ESTIMASI_WAKTU = re.compile(
    r"\b(hitung\s+estimasi|estimasi\s+selesai|estimasi\s+waktu|berapa\s+hari\s+kerja|kapan\s+selesai|"
    r"hitung\s+hari\s+kerja|estimasi\s+tanggal|kalkulasi\s+hari\s+kerja|kalkulator\s+waktu|"
    r"lama\s+proses\s+\d+\s+hari|jika\s+(?:prosesnya\s+)?\d+\s+hari\s+kerja)\b",
    re.IGNORECASE,
)


_RE_DOUBT_OR_CORRECTION = re.compile(
    r"\b(salah|keliru|bukan|bukannya|kok beda|kok salah|kok bisa|kenapa beda|memang iya|masa sih|yakin|beneran|serius|ngaco|bohong|ngibul|gak bener|tidak benar|kurang tepat|tidak tepat|hitung kembali|hitung ulang)\b",
    re.IGNORECASE,
)


def _is_doubt_or_correction_query(text: str) -> bool:
    """Mendeteksi apakah teks pengguna adalah bentuk keraguan, sanggahan, atau koreksi."""
    if not text:
        return False
    return bool(_RE_DOUBT_OR_CORRECTION.search(text))


