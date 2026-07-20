import requests

url = "http://localhost:8000/api/chat/message"
headers = {
    "Authorization": "Bearer your-secure-internal-token-here",
    "Content-Type": "application/json"
}
payload = {
    "phone_number": "6281234567890",
    "message": "Apa syarat mengajukan server baru?"
}

print("Sedang memproses pertanyaan ke LLM...")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    if response.status_code == 200:
        data = response.json()
        print("\n" + "="*50)
        print("[!] JAWABAN FULL DARI AI:")
        print("="*50)
        print(data["reply"])
        print("\n[!] REFERENSI:")
        print(data["sources"])
    else:
        print(f"Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Failed: {e}")
