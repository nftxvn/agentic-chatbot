import requests
import json
import sys

# URL endpoint FastAPI
url = "http://localhost:8000/api/chat/stream"

# Payload request
payload = {
    "session_id": "test-sesi-lokal-1",
    "query": "Apa syarat untuk mengajukan permohonan server baru?" # Bisa diganti dengan pertanyaan lain
}

print(f"Mengirim pertanyaan: '{payload['query']}'")
print("-" * 50)

try:
    # Lakukan request POST dengan stream=True
    with requests.post(url, json=payload, stream=True) as response:
        # Cek jika koneksi berhasil
        if response.status_code != 200:
            print(f"Error: Server merespons dengan status {response.status_code}")
            print(response.text)
            sys.exit(1)
            
        # Parse output SSE
        for line in response.iter_lines():
            if line:
                data_str = line.decode('utf-8')
                try:
                    data = json.loads(data_str)
                    if data["type"] == "chunk":
                        # Print kata per kata
                        sys.stdout.write(data["content"])
                        sys.stdout.flush()
                    elif data["type"] == "done":
                        print("\n\n" + "-" * 50)
                        print("[SELESAI]")
                    elif data["type"] == "error":
                        print(f"\n[ERROR DARI SERVER]: {data['content']}")
                except json.JSONDecodeError:
                    # Abaikan baris yang bukan JSON valid
                    pass
except requests.exceptions.ConnectionError:
    print("[ERROR] Gagal terhubung! Pastikan server FastAPI sudah berjalan di port 8000.")
