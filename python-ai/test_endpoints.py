"""
Test script untuk 3 endpoint baru.

Endpoint yang ditest:
  1. GET  /api/docs              - List semua dokumen
  2. GET  /api/docs/{id}/status  - Cek status dokumen
  3. POST /api/chat/message      - Chat non-streaming (WhatsApp)

Prasyarat:
  - FastAPI server berjalan: uvicorn app.main:app --reload --port 8000
  - Untuk endpoint dokumen: MySQL harus aktif + tabel 'documents' ada
  - Untuk endpoint chat: Ollama + ChromaDB harus aktif + ada data di ChromaDB

Jalankan: python test_endpoints.py
"""

import json
import sys
import requests

# ── Konfigurasi ──────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
API_TOKEN = "your-secure-internal-token-here"  # Sesuaikan dengan .env
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

results = []


def log_result(name: str, passed: bool, detail: str = ""):
    """Catat hasil test."""
    status = "[PASS]" if passed else "[FAIL]"
    results.append((name, passed))
    print(f"  {status} - {name}")
    if detail:
        print(f"         {detail}")


# ── Test 0: Health Check ─────────────────────────────────────────
def test_health():
    print("\n" + "=" * 60)
    print("TEST 0: Health Check")
    print("=" * 60)

    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            log_result("Health check", True, f"status={data['status']}, model={data['model']}")
            return True
        else:
            log_result("Health check", False, f"Status {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log_result("Health check", False, "Server tidak berjalan di port 8000!")
        print("\n  ⚠️  Jalankan dulu: uvicorn app.main:app --reload --port 8000")
        return False


# ── Test 1: GET /api/docs - List Dokumen ─────────────────────────
def test_list_documents():
    print("\n" + "=" * 60)
    print("TEST 1: GET /api/docs - List Semua Dokumen")
    print("=" * 60)

    # Test 1a: Tanpa token (harus 422/401)
    try:
        resp = requests.get(f"{BASE_URL}/api/docs", timeout=5)
        if resp.status_code in (401, 422):
            log_result("Tanpa token -> ditolak", True, f"Status {resp.status_code}")
        else:
            log_result("Tanpa token -> ditolak", False, f"Harusnya 401/422, dapat {resp.status_code}")
    except Exception as e:
        log_result("Tanpa token -> ditolak", False, str(e))

    # Test 1b: Dengan token salah (harus 401)
    try:
        bad_headers = {"Authorization": "Bearer token-salah-banget"}
        resp = requests.get(f"{BASE_URL}/api/docs", headers=bad_headers, timeout=5)
        if resp.status_code == 401:
            log_result("Token salah -> 401", True)
        else:
            log_result("Token salah -> 401", False, f"Dapat {resp.status_code}")
    except Exception as e:
        log_result("Token salah -> 401", False, str(e))

    # Test 1c: Dengan token benar (harus 200)
    try:
        resp = requests.get(f"{BASE_URL}/api/docs", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_result(
                "Token benar -> 200 + data",
                True,
                f"Total dokumen: {data['total']}",
            )
            if data["documents"]:
                doc = data["documents"][0]
                print(f"         Contoh: id={doc['id']}, status={doc['status']}")
        elif resp.status_code == 500:
            detail = resp.json().get("detail", "")
            if "documents" in detail.lower() or "mysql" in detail.lower() or "table" in detail.lower():
                log_result(
                    "Token benar -> 200 + data",
                    False,
                    "MySQL/tabel 'documents' belum siap. Ini normal kalau Laravel belum di-migrate.",
                )
            else:
                log_result("Token benar -> 200 + data", False, f"Status 500: {detail[:100]}")
        else:
            log_result("Token benar -> 200 + data", False, f"Status {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        log_result("Token benar -> 200 + data", False, str(e))


# ── Test 2: GET /api/docs/{id}/status - Status Dokumen ───────────
def test_document_status():
    print("\n" + "=" * 60)
    print("TEST 2: GET /api/docs/{id}/status - Cek Status Dokumen")
    print("=" * 60)

    # Test 2a: Dokumen yang tidak ada (harus 404)
    try:
        resp = requests.get(
            f"{BASE_URL}/api/docs/99999/status",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 404:
            log_result("Dokumen tidak ada -> 404", True)
        elif resp.status_code == 500:
            log_result(
                "Dokumen tidak ada -> 404",
                False,
                "MySQL/tabel belum siap (normal kalau belum migrate)",
            )
        else:
            log_result("Dokumen tidak ada -> 404", False, f"Dapat {resp.status_code}")
    except Exception as e:
        log_result("Dokumen tidak ada -> 404", False, str(e))

    # Test 2b: Dokumen ID 1 (kalau ada)
    try:
        resp = requests.get(
            f"{BASE_URL}/api/docs/1/status",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            log_result(
                "Dokumen ID 1 -> detail status",
                True,
                f"status={data['status']}, pdf_type={data.get('pdf_type')}",
            )
        elif resp.status_code == 404:
            log_result("Dokumen ID 1 -> detail status", True, "Tidak ada (404) - normal untuk DB kosong")
        elif resp.status_code == 500:
            log_result("Dokumen ID 1 -> detail status", False, "MySQL/tabel belum siap")
        else:
            log_result("Dokumen ID 1 -> detail status", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("Dokumen ID 1 -> detail status", False, str(e))


# ── Test 3: POST /api/chat/message - Chat Non-Streaming ─────────
def test_chat_message():
    print("\n" + "=" * 60)
    print("TEST 3: POST /api/chat/message - Chat Non-Streaming (WhatsApp)")
    print("=" * 60)

    # Test 3a: Tanpa token (harus 422/401)
    try:
        payload = {"phone_number": "6281234567890", "message": "Halo"}
        resp = requests.post(
            f"{BASE_URL}/api/chat/message",
            json=payload,
            timeout=5,
        )
        if resp.status_code in (401, 422):
            log_result("Tanpa token -> ditolak", True, f"Status {resp.status_code}")
        else:
            log_result("Tanpa token -> ditolak", False, f"Dapat {resp.status_code}")
    except Exception as e:
        log_result("Tanpa token -> ditolak", False, str(e))

    # Test 3b: Pesan kosong (harus 400)
    try:
        payload = {"phone_number": "6281234567890", "message": "   "}
        resp = requests.post(
            f"{BASE_URL}/api/chat/message",
            json=payload,
            headers=HEADERS,
            timeout=5,
        )
        if resp.status_code == 400:
            log_result("Pesan kosong -> 400", True)
        else:
            log_result("Pesan kosong -> 400", False, f"Dapat {resp.status_code}")
    except Exception as e:
        log_result("Pesan kosong -> 400", False, str(e))

    # Test 3c: Pertanyaan valid (harus 200 + reply)
    try:
        payload = {
            "phone_number": "6281234567890",
            "message": "Apa syarat mengajukan server baru?",
        }
        print("\n  [WAIT] Mengirim pertanyaan ke LLM (bisa 10-30 detik)...")
        resp = requests.post(
            f"{BASE_URL}/api/chat/message",
            json=payload,
            headers=HEADERS,
            timeout=120,  # LLM bisa lama
        )
        if resp.status_code == 200:
            data = resp.json()
            reply_preview = data["reply"][:150].replace("\n", " ")
            log_result(
                "Pertanyaan valid -> 200 + reply",
                True,
                f"Panjang reply: {len(data['reply'])} karakter, sumber: {len(data['sources'])}",
            )
            print(f"         Preview: \"{reply_preview}...\"")
        elif resp.status_code == 500:
            detail = resp.json().get("detail", "")
            if "ollama" in detail.lower() or "connection" in detail.lower():
                log_result("Pertanyaan valid -> 200 + reply", False, "Ollama tidak berjalan!")
            else:
                log_result("Pertanyaan valid -> 200 + reply", False, f"Error: {detail[:100]}")
        else:
            log_result("Pertanyaan valid -> 200 + reply", False, f"Status {resp.status_code}")
    except requests.exceptions.ReadTimeout:
        log_result("Pertanyaan valid -> 200 + reply", False, "Timeout (>120 detik). LLM terlalu lambat?")
    except Exception as e:
        log_result("Pertanyaan valid -> 200 + reply", False, str(e))


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TEST ENDPOINT BARU")
    print("  GET /api/docs | GET /api/docs/{id}/status | POST /api/chat/message")
    print("=" * 60)

    # Cek server dulu
    if not test_health():
        print("\n❌ Server tidak aktif. Jalankan dulu:")
        print("   cd python-ai")
        print("   uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    # Jalankan semua test
    test_list_documents()
    test_document_status()
    test_chat_message()

    # Ringkasan
    print("\n" + "=" * 60)
    print("  RINGKASAN HASIL TEST")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        icon = "[PASS]" if ok else "[FAIL]"
        print(f"  {icon} {name}")

    print(f"\n  Hasil: {passed}/{total} test berhasil")

    if passed == total:
        print("  *** SEMUA TEST LULUS! ***")
    else:
        print("  !!! Ada test yang gagal - lihat detail di atas. !!!")
    print("=" * 60)
