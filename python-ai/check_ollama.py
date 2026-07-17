import requests, json, sys

BASE = "http://localhost:11434"

# 1. Cek model apa saja yang tersedia
print("=== Model tersedia di Ollama ===")
r = requests.get(f"{BASE}/api/tags", timeout=5)
models = r.json().get("models", [])
for m in models:
    print(f"  - {m['name']}")

# 2. Baca konfigurasi yang dipakai app
sys.path.insert(0, ".")
from app.config import settings
print(f"\nLLM_MODEL_NAME   : {settings.LLM_MODEL_NAME}")
print(f"VISION_MODEL_NAME: {settings.VISION_MODEL_NAME}")

# 3. Cek apakah VISION_MODEL_NAME ada di Ollama
vision_model = settings.VISION_MODEL_NAME
available_names = [m["name"] for m in models]
found = any(vision_model in n for n in available_names)
print(f"\nVISION_MODEL_NAME '{vision_model}' tersedia? {'YA' if found else 'TIDAK'}")

# 4. Cek error 400 dengan mengirim request percobaan minimal
print(f"\n=== Test request ke /api/generate (model: {vision_model}) ===")
import base64
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
payload = {
    "model": vision_model,
    "prompt": "What do you see?",
    "images": [base64.b64encode(MINIMAL_PNG).decode()],
    "stream": False,
}
try:
    resp = requests.post(f"{BASE}/api/generate", json=payload, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")
