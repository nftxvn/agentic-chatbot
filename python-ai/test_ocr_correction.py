import requests
import json

# Konfigurasi Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

# Contoh hasil OCR yang kotor (banyak typo, angka nyasar, spasi terputus)
dirty_text = """
Syar at peng aju an s3rver bar u di Diskom inf otik:
1. Mengisi for mulir P ermintaan Infra struktur lT (F orm -IT-00 1).
2. Men dapat perset ujuan dari a tasan Iangsung.
"""

prompt = f"""
Anda adalah asisten AI pengoreksi teks.
Berikut adalah teks hasil ekstraksi OCR dokumen berbahasa Indonesia yang memiliki salah ketik (typo) dan spasi yang berantakan.
Tugas Anda: Perbaiki semua typo, satukan pemenggalan kata yang salah, dan rapikan kalimatnya menjadi bahasa Indonesia yang baku.
JANGAN tambahkan komentar, penjelasan, atau teks pengantar apapun. Langsung berikan teks hasil perbaikannya saja.

Teks asli:
{dirty_text}
"""

payload = {
    "model": MODEL_NAME,
    "prompt": prompt,
    "stream": False
}

print("==================================================")
print("  TEKS ASLI (SEBELUM KOREKSI)")
print("==================================================")
print(dirty_text.strip())
print("\n[Mengeksekusi AI untuk mengoreksi teks...]")

try:
    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()
    
    print("\n==================================================")
    print("  TEKS BERSIH (SETELAH KOREKSI)")
    print("==================================================")
    print(result["response"].strip())
except Exception as e:
    print(f"Error: {e}")
