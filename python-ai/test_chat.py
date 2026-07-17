import requests
import json
import sys

# URL endpoint FastAPI
url = "http://localhost:8000/api/chat/stream"

# Payload request
payload = {
    "session_id": "test-sesi-lokal-1",
    "query": "Apa isi diktum kesatu?" # Bisa diganti dengan pertanyaan lain
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
                # SSE format: setiap baris diawali "data: ", harus dibuang dulu
                if data_str.startswith("data: "):
                    data_str = data_str[len("data: "):]
                else:
                    continue  # skip baris yang bukan data SSE
                try:
                    data = json.loads(data_str)
                    if data["type"] == "chunk":
                        # Encode safe agar tidak error di terminal Windows
                        content = data["content"].encode("ascii", errors="replace").decode("ascii")
                        sys.stdout.write(content)
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
