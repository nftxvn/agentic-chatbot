"""
Ingest dokumen ke ChromaDB langsung dari baris perintah.

Melewati Celery, Redis, dan MySQL — cukup jalankan skripnya. Berguna untuk
mengulang ingest setelah ekstraksi diperbaiki, tanpa menyalakan seluruh
tumpukan layanan.

DIRANCANG SUPAYA KORPUS TIDAK PERNAH KOSONG. Ekstraksi dan pemotongan
diselesaikan LEBIH DULU, hasilnya dilaporkan, baru vektor lama dihapus tepat
sebelum yang baru disimpan. Urutan itu penting: pernah terjadi penghapusan
dilakukan di awal lalu prosesnya berhenti di tengah OCR, dan korpus tertinggal
kosong selama berjam-jam.

Ekstraksi disimpan ke data/ekstraksi_<id>.json. OCR halaman pindai memakan
waktu paling lama, jadi mengulang dengan --pakai-ekstraksi melewatinya.

Pemakaian:
    python ingest_dokumen.py --file "test_files/SOP.pdf" --id 1
    python ingest_dokumen.py --file "..." --id 1 --pratinjau     # tidak menyimpan
    python ingest_dokumen.py --id 1 --pakai-ekstraksi            # pakai hasil OCR lama
    python ingest_dokumen.py --id 1 --pakai-koreksi              # pakai koreksi manual
    python ingest_dokumen.py --file "..." --id 1 --pratinjau --tuang
    python ingest_dokumen.py --file "..." --id 1 --tuang --tuang-ke lain.md

--tuang menulis teks mentah tiap halaman ke Markdown (bawaan
chroma_db_contents.md) supaya hasil OCR bisa dibaca mata sendiri, bukan cuma
sebagai JSON. Berkas itu juga dipakai `test_chromadb.py --tuang` untuk menuang
KORPUS; judul di baris pertama selalu menyebut mana yang sedang dilihat.

Penanda daftar yang huruf ulangnya rontok saat OCR ikut dipulihkan pada kedua
jalur — termasuk saat memakai ekstraksi lama, sehingga korpus bisa diperbaiki
tanpa mengulang OCR.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="  %(message)s")
for _bising in ("chromadb", "chromadb.telemetry", "posthog", "backoff", "httpx"):
    logging.getLogger(_bising).setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

DIR_EKSTRAKSI = Path("data")

# Tujuan `--tuang`. Berkas yang sama dipakai `test_chromadb.py --tuang` untuk
# menuang KORPUS; keduanya menulis judul yang menyebutkan dirinya sendiri,
# jadi yang terakhir menulis selalu bisa dikenali dari baris pertama.
# Berkas kerja koreksi manual. Ditulis oleh --tuang, dibaca oleh --pakai-koreksi.
BERKAS_TUANG = "hasil_ekstraksi.md"


def _arg(nama: str, bawaan: str | None = None) -> str | None:
    for i, a in enumerate(sys.argv):
        if a == nama and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(nama + "="):
            return a.split("=", 1)[1]
    return bawaan


def laporkan_halaman(pages: list[dict]) -> None:
    """
    Cetak keadaan tiap halaman SEBELUM korpus disentuh.

    Dua hal yang paling sering salah dan paling mahal kalau lolos: baris
    'Nama SOP' yang hilang saat OCR (halaman jadi tak berlabel, lalu pertanyaan
    tentangnya mendarat di halaman tetangga), dan penanda daftar yang huruf
    ulangnya rontok.
    """
    print(f"\n  {len(pages)} halaman terekstrak:\n")
    print(f"    {'Hal':>4}  {'Huruf':>6}  {'Item':>5}  Nama SOP")
    print(f"    {'-' * 4}  {'-' * 6}  {'-' * 5}  {'-' * 46}")

    tanpa_nama = []
    for h in pages:
        teks = h["text"]
        nomor = h["page_number"]
        m = re.search(r"Nama\s+SOP\s*[:|]\s*(.+)", teks, re.IGNORECASE)
        item = len(re.findall(r"(?m)^\s*[a-zA-Z]{1,4}\.\s+\S", teks))
        nama = m.group(1).strip()[:46] if m else "—"
        if not m and "Nomor SOP" in teks:
            tanpa_nama.append(nomor)
            nama = "!! HILANG padahal ada 'Nomor SOP'"
        print(f"    {nomor:>4}  {len(teks):>6}  {item:>5}  {nama}")

    if tanpa_nama:
        print(
            f"\n  PERINGATAN: halaman {tanpa_nama} memuat 'Nomor SOP' tetapi tidak"
            "\n  'Nama SOP'. Halaman itu akan tersimpan TANPA label, dan pertanyaan"
            "\n  tentangnya cenderung mendarat di halaman tetangganya. Pertimbangkan"
            "\n  mengulang ekstraksi sebelum menyimpan."
        )
    print()


def tuang_ekstraksi(
    pages: list[dict],
    doc_id: int,
    berkas_sumber: str,
    keluaran: str,
    masuk_korpus: bool,
    induk: list[dict] | None = None,
    anak: list[dict] | None = None,
) -> None:
    """
    Tulis hasil ekstraksi ke Markdown yang BISA DISUNTING MANUSIA.

    Tiap halaman ditulis dua kali dengan peran berbeda:

      * blok `OCR asli` — rujukan, dilipat, tidak pernah dibaca kembali
      * blok `KOREKSI`  — sudah terisi teks OCR, dan INILAH yang dibaca ulang
        oleh `--pakai-koreksi`

    Kenapa dua kali dan bukan sekali: mengoreksi tanpa pembanding berarti
    menebak apa yang berubah. Dengan aslinya tersimpan di halaman yang sama,
    kesalahan OCR bisa dilihat berdampingan dengan perbaikannya, dan berkas ini
    tetap jadi catatan apa yang model baca — bukan cuma apa yang akhirnya dipakai.

    Konteks halaman ikut dicantumkan karena label itulah yang menentukan sebuah
    halaman bisa ditemukan atau tidak. Kalau labelnya salah, itu paling cepat
    ketahuan saat teks halamannya dibaca manusia — bukan setelah masuk korpus.
    """
    # Ambang jalur chunking diambil dari chunker itu sendiri, bukan ditulis
    # ulang di sini: tabel yang tidak sepakat dengan sistemnya lebih buruk
    # daripada tabel yang tidak ada.
    from app.services.embedding_service import (
        _LIST_BLOCK_HARD_CAP,
        _LIST_ITEM_THRESHOLD,
        _list_item_boundary,
    )

    induk = induk or []
    anak = anak or []

    konteks_per_halaman: dict[int, str] = {}
    for c in induk:
        for baris in c["text"].split("\n"):
            if baris.startswith("[Konteks:"):
                konteks_per_halaman[c["page_number"]] = baris[9:].rstrip("]").strip()
                break

    baris: list[str] = []
    tulis = baris.append

    total = sum(len(h["text"]) for h in pages)
    status = (
        "vektor sudah diganti dengan hasil ini"
        if masuk_korpus
        else "**belum masuk korpus** — masih bisa dikoreksi"
    )

    tulis(f"# Hasil ekstraksi dokumen #{doc_id} — {datetime.now():%Y-%m-%d %H:%M}\n")
    tulis("## Cara mengoreksi\n")
    tulis(
        "1. Sunting **hanya** isi blok ```` ```text ```` di bawah judul "
        "`KOREKSI halaman N`. Blok `OCR asli` biarkan apa adanya — ia rujukan.\n"
        "2. Jangan mengubah baris judul `### KOREKSI halaman N`; baris itu yang "
        "dipakai untuk menemukan potongan Anda saat dibaca kembali.\n"
        "3. Setelah selesai, jalankan:\n\n"
        f"       python ingest_dokumen.py --id {doc_id} --pakai-koreksi\n\n"
        "   Teks di blok KOREKSI itulah yang dipotong jadi induk/anak lalu "
        "di-embed. Blok yang tidak Anda sentuh tetap terpakai apa adanya.\n"
    )

    tulis("| | Nilai |")
    tulis("|---|---|")
    tulis(f"| Berkas sumber | `{berkas_sumber}` |")
    tulis(f"| Halaman | **{len(pages)}** |")
    tulis(f"| Total karakter | {total:,} |".replace(",", "."))
    tulis(f"| Status | {status} |")
    tulis("")

    tulis("\n## Ringkasan\n")
    tulis("| Hal | Karakter | Item | Jalur chunking | Konteks |")
    tulis("|---:|---:|---:|---|---|")
    for h in pages:
        teks = h["text"]
        nomor = h["page_number"]
        item = len(_list_item_boundary.findall(teks))
        if item >= _LIST_ITEM_THRESHOLD:
            jalur = (
                "daftar utuh"
                if len(teks) <= _LIST_BLOCK_HARD_CAP
                else "daftar dipecah di batas item"
            )
        else:
            jalur = "entri prosedur / splitter"
        tulis(
            f"| {nomor} | {len(teks)} | {item} | {jalur} "
            f"| {konteks_per_halaman.get(nomor, '—')} |"
        )
    tulis("")

    for h in pages:
        nomor = h["page_number"]
        tulis(f"\n---\n\n## Halaman {nomor}\n")
        tulis(f"- Konteks: **{konteks_per_halaman.get(nomor, '—')}**")
        tulis(f"- {len(h['text'])} karakter\n")

        tulis("<details>")
        tulis("<summary>OCR asli — rujukan, jangan diubah</summary>\n")
        tulis("```text")
        tulis(h["text"])
        tulis("```")
        tulis("</details>\n")

        tulis(f"### KOREKSI halaman {nomor}\n")
        tulis("```text")
        tulis(h["text"])
        tulis("```")
    tulis("")

    Path(keluaran).write_text("\n".join(baris), encoding="utf-8")

    ukuran = Path(keluaran).stat().st_size / 1024
    print(f"  Ditulis ke {keluaran} ({ukuran:.0f} KB) — {len(pages)} halaman siap dikoreksi")


# Judul blok koreksi. Nomor halamannya yang menjadi kunci pembacaan ulang,
# jadi baris ini sengaja kaku: sekali berubah, potongannya tidak ditemukan.
_POLA_BLOK_KOREKSI = re.compile(
    r"^###[ \t]+KOREKSI[ \t]+halaman[ \t]+(\d+)[ \t]*$", re.MULTILINE | re.IGNORECASE
)


def baca_koreksi(berkas: str) -> list[dict]:
    """
    Baca kembali berkas Markdown yang sudah dikoreksi manusia.

    Yang diambil HANYA blok berpagar ```text pertama sesudah tiap judul
    `### KOREKSI halaman N`. Blok `OCR asli` berada di dalam <details> SEBELUM
    judul itu, jadi ia tidak pernah ikut terbaca.

    Gagal keras bila ada halaman yang bloknya kosong. Halaman kosong tidak
    menimbulkan galat di tahap mana pun sesudah ini — ia hanya lenyap dari
    korpus tanpa jejak, dan baru ketahuan lewat jawaban 'tidak ditemukan'
    berhari-hari kemudian.
    """
    if not Path(berkas).exists():
        raise SystemExit(
            f"  Tidak ada {berkas}. Buat dulu dengan --tuang, koreksi isinya, "
            "baru jalankan --pakai-koreksi."
        )

    isi = Path(berkas).read_text(encoding="utf-8")
    penanda = list(_POLA_BLOK_KOREKSI.finditer(isi))
    if not penanda:
        raise SystemExit(
            f"  {berkas} tidak memuat satu pun '### KOREKSI halaman N'. "
            "Berkas ini bukan hasil --tuang, atau judul bloknya sudah diubah."
        )

    pages: list[dict] = []
    kosong: list[int] = []

    for i, m in enumerate(penanda):
        nomor = int(m.group(1))
        batas = penanda[i + 1].start() if i + 1 < len(penanda) else len(isi)
        potongan = isi[m.end():batas]

        pagar = re.search(r"```(?:text)?[ \t]*\n(.*?)\n```", potongan, re.DOTALL)
        teks = pagar.group(1).strip() if pagar else ""
        if not teks:
            kosong.append(nomor)
            continue

        pages.append({"page_number": nomor, "text": teks})

    if kosong:
        raise SystemExit(
            f"  Blok KOREKSI halaman {kosong} kosong. Isi dulu, atau hapus judul "
            "bloknya bila halaman itu memang tidak ingin dimasukkan."
        )

    pages.sort(key=lambda h: h["page_number"])
    return pages


def main() -> None:
    berkas = _arg("--file")
    doc_id = int(_arg("--id", "1"))
    pratinjau = "--pratinjau" in sys.argv
    pakai_lama = "--pakai-ekstraksi" in sys.argv
    pakai_koreksi = "--pakai-koreksi" in sys.argv
    tuang = "--tuang" in sys.argv
    tuang_ke = _arg("--tuang-ke") or BERKAS_TUANG

    DIR_EKSTRAKSI.mkdir(exist_ok=True)
    simpanan = DIR_EKSTRAKSI / f"ekstraksi_{doc_id}.json"

    print("\n" + "=" * 66)
    print(f"  INGEST DOKUMEN — id={doc_id}")
    print("=" * 66)

    # ── 1. Ekstraksi ────────────────────────────────────────────
    if pakai_koreksi:
        berkas_koreksi = _arg("--pakai-koreksi")
        if not berkas_koreksi or berkas_koreksi.startswith("--"):
            berkas_koreksi = tuang_ke
        pages = baca_koreksi(berkas_koreksi)
        sumber = f"{berkas_koreksi} (sudah dikoreksi manual)"
        print(f"  Memakai koreksi manual: {berkas_koreksi}")
        print(f"  {len(pages)} halaman terbaca dari blok KOREKSI")
    elif pakai_lama:
        if not simpanan.exists():
            raise SystemExit(f"  Tidak ada ekstraksi tersimpan di {simpanan}")
        pages = json.loads(simpanan.read_text(encoding="utf-8"))
        sumber = f"{simpanan} (ekstraksi tersimpan, tanpa OCR ulang)"
        print(f"  Memakai ekstraksi tersimpan: {simpanan}")

        # Perbaikan penanda daftar biasanya berjalan di dalam extract_text,
        # yang dilewati di jalur ini. Ekstraksi lama karena itu masih membawa
        # penanda rusaknya, jadi perbaikannya dijalankan ulang di sini — justru
        # inilah kasus paling berguna untuk --pakai-ekstraksi: memulihkan korpus
        # tanpa mengulang OCR yang memakan puluhan menit.
        from app.services.pdf_processor import perbaiki_penanda_daftar

        diperbaiki = perbaiki_penanda_daftar(pages)
        if diperbaiki:
            print(f"  {diperbaiki} penanda daftar dipulihkan dari ekstraksi lama")
    else:
        if not berkas:
            raise SystemExit(
                "  --file wajib diisi. Contoh:"
                '  python ingest_dokumen.py --file "test_files/SOP.pdf" --id 1'
                "  (atau --pakai-ekstraksi untuk memakai hasil OCR sebelumnya)"
            )
        if not Path(berkas).exists():
            raise SystemExit(f"  Berkas tidak ditemukan: {berkas}")

        from app.services import pdf_processor

        print(f"  Mengekstrak '{berkas}' ...")
        print("  Halaman pindai lewat OCR — bagian ini yang paling lama.")
        print()
        mulai = time.perf_counter()
        pages = pdf_processor.extract_text(berkas)
        sumber = berkas
        print(f"  Ekstraksi selesai dalam {time.perf_counter() - mulai:.0f} detik")
        simpanan.write_text(
            json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Disimpan ke {simpanan} — ulangi cepat dengan --pakai-ekstraksi")

    laporkan_halaman(pages)

    # ── 2. Pemotongan ───────────────────────────────────────────
    from app.services import embedding_service as es

    judul = es.derive_document_title(pages)
    print(f"  Judul dokumen: {judul or '(tidak terdeteksi)'}")

    induk, anak = es.chunk_text_hierarchical(pages, document_title=judul)
    print(f"  Potongan siap: {len(induk)} induk, {len(anak)} anak")

    if pratinjau:
        if tuang:
            tuang_ekstraksi(pages, doc_id, sumber, tuang_ke, False, induk, anak)
        print("\n  --pratinjau aktif: korpus TIDAK disentuh sama sekali.\n")
        return

    # ── 3. Ganti isi korpus ─────────────────────────────────────
    # Penghapusan sengaja ditaruh SEBERSEBELAH mungkin dengan penyimpanan,
    # supaya jeda korpus-kosong sesingkat mungkin bila terjadi kegagalan.
    lama = es.get_chroma_collection().count()
    print(f"\n  Vektor saat ini: {lama}. Mengganti isi dokumen id={doc_id} ...")

    dihapus = es.delete_document_vectors(doc_id)
    tersimpan = es.embed_and_store_hierarchical(doc_id, induk, anak)

    baru = es.get_chroma_collection().count()
    print(f"\n  Dihapus  : {dihapus} vektor lama")
    print(f"  Disimpan : {tersimpan} vektor baru")
    print(f"  Total    : {baru} vektor di korpus")
    if tuang:
        tuang_ekstraksi(pages, doc_id, sumber, tuang_ke, True, induk, anak)

    print("\n  Periksa hasilnya:  python test_chromadb.py\n")


if __name__ == "__main__":
    main()
