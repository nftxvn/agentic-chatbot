"""
debug_vision_ollama.py

Script sementara untuk mendiagnosis error 400 Bad Request dari Ollama
saat memanggil vision model. Jalankan langsung: python debug_vision_ollama.py
"""

import base64
import json

import fitz
import requests

from app.config import settings

# Ganti dengan path PDF yang dipakai di test kamu (yang bikin test_10 gagal)
PDF_PATH = "test_files/SOP-diskominfotik-2025.pdf"  # <-- sesuaikan
PAGE_INDEX = 1  # halaman pertama


def main():
    print("VISION_MODEL_NAME:", settings.VISION_MODEL_NAME)
    print("OLLAMA_BASE_URL:", settings.OLLAMA_BASE_URL)

    # Cek daftar model yang tersedia di Ollama
    tags_resp = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
    print("\n--- Model tersedia di Ollama ---")
    for m in tags_resp.json().get("models", []):
        print(" -", m["name"])

    # Render halaman PDF ke image
    doc = fitz.open(PDF_PATH)
    page = doc[PAGE_INDEX]
    pixmap = page.get_pixmap(dpi=150)
    img_bytes = pixmap.tobytes("png")
    image_b64 = base64.b64encode(img_bytes).decode("utf-8")
    doc.close()

    print("\nUkuran gambar (bytes):", len(img_bytes))
    print("Panjang base64:", len(image_b64))

    payload = {
        "model": settings.VISION_MODEL_NAME,
        "prompt": (
            "You are an OCR tool. Read and extract ALL text visible in this document image. "
            "Preserve the original structure: paragraphs, line breaks, and tables. "
            "For tables, use spaces or the | character to separate columns. "
            "Output only the extracted text — no explanations, no comments, nothing else."
        ),
        "images": [image_b64],
        "stream": False,
    }

    print("\n--- Mengirim request ke Ollama ---")
    resp = requests.post(
    f"{settings.OLLAMA_BASE_URL}/api/generate",
    json=payload,
    timeout=300,   # naikkan ke 5 menit untuk percobaan pertama

    )

    print("Status code:", resp.status_code)
    print("Response body:")
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()