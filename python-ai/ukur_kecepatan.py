#!/usr/bin/env python3
"""
Ukur kecepatan chat dalam kondisi kerja yang SEBENARNYA.

Dipakai untuk menjawab satu pertanyaan: setelan mana yang stabil di mesin ini?
Jalankan saat Claude Code TIDAK menyala — sesi Claude Code sendiri memakai ~2 GB
RAM, cukup untuk memicu swap di mesin 8 GiB dan membuat hasilnya menyesatkan.

    cd python-ai
    ./venv/bin/python ukur_kecepatan.py

Yang dilaporkan per permintaan: waktu total, jeda sampai token pertama,
kecepatan, lalu keadaan swap dan VRAM. Yang perlu diperhatikan bukan angka
tertingginya, melainkan SEBARANNYA — kecepatan yang berayun jauh menandakan
memori sedang bolak-balik ke disk, bukan GPU yang lambat.
"""

import json
import subprocess
import time
import urllib.request

URL = "http://localhost:8080/api/chat/stream"

PERTANYAAN = [
    "Apa saja persyaratan untuk mengurus surat izin?",
    "Berapa waktu yang diperlukan untuk SOP perjalanan dinas?",
    "Sebutkan tahapan pengajuan surat keterangan.",
]


def keadaan() -> str:
    """Swap terpakai dan VRAM bebas — dua angka yang menjelaskan hasil aneh."""
    try:
        swap = subprocess.run(["free", "-m"], capture_output=True, text=True
                              ).stdout.split("\n")[2].split()[2]
    except Exception:
        swap = "?"
    try:
        vram = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip() or "?"
    except Exception:
        vram = "tanpa GPU"
    return f"swap {swap} MiB · VRAM bebas {vram} MiB"


def satu(pertanyaan: str, sesi: str) -> float | None:
    """Kirim satu pertanyaan, hitung token dari aliran SSE. None bila gagal."""
    body = json.dumps({"session_id": sesi, "query": pertanyaan}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})

    n, t0, mulai = 0, None, time.time()
    try:
        for baris in urllib.request.urlopen(req, timeout=600):
            teks = baris.decode("utf-8", "replace").strip()
            if not teks.startswith("data: "):
                continue
            try:
                data = json.loads(teks[6:])
            except json.JSONDecodeError:
                continue
            if data.get("type") == "chunk" and data.get("content"):
                if t0 is None:
                    t0 = time.time()
                n += 1
    except Exception as e:
        print(f"     GAGAL: {type(e).__name__} — layanan di port 8080 hidup?")
        return None

    if not n or t0 is None:
        print("     GAGAL: tidak ada token diterima.")
        return None

    selesai = time.time()
    laju = n / (selesai - t0)
    print(f"     total {selesai - mulai:5.1f} dtk · token pertama {t0 - mulai:5.1f} dtk · "
          f"{n:4d} token @ {laju:5.2f} tok/dtk")
    print(f"     {keadaan()}")
    return laju


def main() -> None:
    print(f"Kondisi awal: {keadaan()}\n")
    print("Permintaan pertama menanggung pemuatan model (bisa 30-80 detik).")
    print("Yang dipakai menilai adalah permintaan KEDUA dan seterusnya.\n")

    hasil = []
    for i, q in enumerate(PERTANYAAN, 1):
        print(f"  #{i} {q}")
        laju = satu(q, f"ukur-{int(time.time())}-{i}")
        if laju is not None:
            hasil.append(laju)
        print()

    tetap = hasil[1:] or hasil
    if not tetap:
        print("Tidak ada hasil yang bisa dinilai.")
        return

    rendah, tinggi = min(tetap), max(tetap)
    print(f"Rata-rata (tanpa permintaan pertama) : {sum(tetap) / len(tetap):.2f} tok/dtk")
    print(f"Sebaran                              : {rendah:.2f} - {tinggi:.2f} tok/dtk")

    # Sebaran lebar adalah gejala paging, bukan GPU lambat. Ambang 40% dipilih
    # dari pengamatan 2026-09-03: saat sehat sebarannya ~15%, saat memori
    # terdesak kecepatan sesaat berayun 0,2-9 tok/dtk.
    if rendah > 0 and (tinggi - rendah) / rendah > 0.4:
        print("\n  PERHATIAN: sebarannya lebar. Biasanya ini tanda memori sedang")
        print("  bolak-balik ke disk, bukan GPU yang lambat. Periksa angka swap")
        print("  di atas; bila naik antar-permintaan, coba 'sudo sysctl vm.swappiness=10'.")
    else:
        print("\n  Sebarannya rapat — kecepatan ini bisa dipercaya sebagai angka mesin.")


if __name__ == "__main__":
    main()
