"""
make_test_pdf.py

Membuat PDF sample untuk testing vision extraction:
- Halaman 1: teks native biasa (PyMuPDF bisa baca langsung)
- Halaman 2: gambar berisi teks (simulasi hasil scan, tanpa text layer)
  -> ini yang akan memicu pemanggilan vision model (LLaVA/Qwen2.5-VL)

Jalankan: python make_test_pdf.py
Hasil: test_files/sample.pdf
"""

import os

import fitz
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "test_files"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sample.pdf")


def create_scanned_page_image() -> str:
    """Buat gambar berisi teks (simulasi halaman hasil scan), simpan sebagai PNG."""
    img = Image.new("RGB", (1200, 1600), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except Exception:
        font = ImageFont.load_default()

    lines = [
        "LAPORAN PENGADUAN IT SUPPORT",
        "",
        "Nomor Tiket   : TCK-2026-00123",
        "Tanggal       : 16 Juli 2026",
        "Pelapor       : Hafizh",
        "Departemen    : Backend Engineering",
        "",
        "Deskripsi Masalah:",
        "Koneksi VPN kantor sering terputus saat",
        "mengakses server database internal pada",
        "jam kerja pukul 09.00 - 11.00 WIB.",
        "",
        "Status        : Sedang diproses",
        "Prioritas     : Tinggi",
    ]

    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 60

    img_path = os.path.join(OUTPUT_DIR, "_scan_page.png")
    img.save(img_path)
    return img_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    doc = fitz.open()

    # --- Halaman 1: teks native ---
    page1 = doc.new_page()
    page1.insert_text(
        (72, 100),
        "Ini adalah halaman dengan teks native.\n"
        "PyMuPDF bisa langsung membaca teks ini tanpa vision model.\n"
        "Dokumen ini dibuat untuk keperluan testing pipeline RAG.",
        fontsize=14,
    )

    # --- Halaman 2: gambar (simulasi hasil scan) ---
    img_path = create_scanned_page_image()
    page2 = doc.new_page()
    rect = fitz.Rect(0, 0, page2.rect.width, page2.rect.height)
    page2.insert_image(rect, filename=img_path)

    doc.save(OUTPUT_PATH)
    doc.close()

    os.remove(img_path)  # bersihkan file PNG sementara

    print(f"PDF sample berhasil dibuat: {OUTPUT_PATH}")
    print("- Halaman 1: teks native")
    print("- Halaman 2: gambar/scan (akan memicu vision model)")


if __name__ == "__main__":
    main()