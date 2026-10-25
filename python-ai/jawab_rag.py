"""
Jalankan pertanyaan lewat pipeline RAG, tulis jawabannya ke hasil_rag.md.

Berbeda dari hasil_ekstraksi.md yang ditulis `ingest_dokumen.py --tuang`:
berkas ini menangkap apa yang terjadi SESUDAH korpus terisi. Keduanya sengaja
terpisah karena dibaca untuk keperluan berbeda — yang satu untuk mengoreksi
bahan mentah sebelum masuk, yang satu untuk menilai jawaban yang keluar.

Butuh Ollama menyala dan korpus sudah terisi.

Pemakaian:
    python jawab_rag.py "Apa saja langkah SOP Renstra?"
    python jawab_rag.py --berkas pertanyaan.txt      # satu pertanyaan per baris
    python jawab_rag.py                              # daftar bawaan di bawah
    python jawab_rag.py "..." --keluaran lain.md
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.WARNING, format="  %(message)s")
for _bising in ("chromadb", "chromadb.telemetry", "posthog", "backoff", "httpx"):
    logging.getLogger(_bising).setLevel(logging.CRITICAL)

BERKAS_KELUARAN = "hasil_rag.md"

# Daftar bawaan sengaja mencampur tiga bentuk yang menekan sisi berbeda:
# pertanyaan terbuka, pertanyaan berjumlah, dan premis palsu. Menjalankan
# ketiganya sekaligus membuat kemunduran terlihat tanpa perlu dataset penuh.
PERTANYAAN_BAWAAN = [
    "Apa saja langkah dalam SOP Penyusunan Renstra?",
    "Berapa jumlah SOP yang ditetapkan dalam keputusan ini?",
    "Siapa yang mengesahkan SOP Penyusunan Renja?",
    "Apa isi Diktum KEEMPAT?",
]


def _arg(nama: str, bawaan: str | None = None) -> str | None:
    for i, a in enumerate(sys.argv):
        if a == nama and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(nama + "="):
            return a.split("=", 1)[1]
    return bawaan


def kumpulkan_pertanyaan() -> list[str]:
    berkas = _arg("--berkas")
    if berkas:
        if not Path(berkas).exists():
            raise SystemExit(f"  Tidak ada berkas pertanyaan: {berkas}")
        return [
            b.strip()
            for b in Path(berkas).read_text(encoding="utf-8").splitlines()
            if b.strip() and not b.lstrip().startswith("#")
        ]

    # Argumen bebas: apa pun yang bukan bendera dan bukan nilai sebuah bendera.
    bendera_bernilai = {"--berkas", "--keluaran"}
    bebas: list[str] = []
    lewati = False
    for a in sys.argv[1:]:
        if lewati:
            lewati = False
            continue
        if a in bendera_bernilai:
            lewati = True
            continue
        if a.startswith("--"):
            continue
        bebas.append(a)

    return bebas or PERTANYAAN_BAWAAN


def main() -> None:
    pertanyaan = kumpulkan_pertanyaan()
    keluaran = _arg("--keluaran") or BERKAS_KELUARAN

    print(f"\n  {len(pertanyaan)} pertanyaan — memuat pipeline ...")
    from app.services import rag_service

    baris: list[str] = []
    tulis = baris.append

    tulis(f"# Hasil RAG — {datetime.now():%Y-%m-%d %H:%M}\n")
    tulis(
        "> Ditulis otomatis oleh `jawab_rag.py`. Jawaban disalin **apa adanya**, "
        "termasuk saat sistem menolak menjawab — penolakan adalah hasil yang sah "
        "dan justru perlu terbaca, bukan disembunyikan.\n"
    )
    tulis(f"| Pertanyaan | {len(pertanyaan)} |")
    tulis("|---|---|")
    tulis("")

    ringkas: list[tuple[str, float, int]] = []

    for n, q in enumerate(pertanyaan, 1):
        print(f"  [{n}/{len(pertanyaan)}] {q[:66]}")
        mulai = time.perf_counter()
        try:
            jawaban = "".join(rag_service.generate_response(q, session_id=f"jawab_rag_{n}"))
            galat = None
        except Exception as e:  # noqa: BLE001 - dicatat, bukan ditelan
            jawaban, galat = "", f"{type(e).__name__}: {e}"
        detik = time.perf_counter() - mulai

        ringkas.append((q, detik, len(jawaban)))

        tulis(f"\n---\n\n## {n}. {q}\n")
        tulis(f"*{detik:.1f} detik · {len(jawaban)} karakter*\n")
        if galat:
            tulis(f"> **GAGAL** — {galat}\n")
        else:
            tulis(jawaban if jawaban.strip() else "> *(jawaban kosong)*")
        tulis("")

    # Ringkasan ditaruh di atas supaya terbaca lebih dulu, tapi baru bisa
    # disusun setelah semuanya selesai.
    tabel = ["\n## Ringkasan\n", "| # | Pertanyaan | Detik | Karakter |", "|---:|---|---:|---:|"]
    for i, (q, detik, panjang) in enumerate(ringkas, 1):
        tabel.append(f"| {i} | {q[:64]} | {detik:.1f} | {panjang} |")
    tabel.append("")
    baris[5:5] = tabel

    Path(keluaran).write_text("\n".join(baris), encoding="utf-8")

    total = sum(d for _, d, _ in ringkas)
    print(f"\n  Ditulis ke {keluaran} — {len(pertanyaan)} jawaban, {total:.0f} detik total\n")


if __name__ == "__main__":
    main()
