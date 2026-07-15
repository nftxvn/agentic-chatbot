"""
Script test lengkap untuk RAG pipeline.

Tahap:
1. Test embedding model (SentenceTransformer)
2. Inject dokumen sample ke ChromaDB (tanpa perlu PDF sungguhan)
3. Test RAG chat via HTTP ke FastAPI
4. Cek hasil retrieval

Jalankan: python test_rag_full.py
"""

from starlette import responses
import json
import sys
import requests

# ─── Konfigurasi ──────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
CHROMA_DIR = "./data/chromadb"

# Data sample yang akan dimasukkan ke ChromaDB
SAMPLE_DOCS = [
    {
        "doc_id": 1,
        "page": 1,
        "text": (
            "Syarat pengajuan server baru di Diskominfotik: "
            "1. Mengisi formulir permintaan infrastruktur IT (Form-IT-001). "
            "2. Mendapat persetujuan Kepala Bidang. "
            "3. Melampirkan justifikasi kebutuhan server minimal 2 halaman. "
            "4. Anggaran harus sudah tercantum dalam DIPA tahun berjalan. "
            "5. Mengajukan ke Kepala Dinas untuk persetujuan akhir."
        ),
    },
    {
        "doc_id": 1,
        "page": 2,
        "text": (
            "Prosedur pengajuan email dinas: "
            "1. Isi formulir Form-EMAIL-003. "
            "2. Lampirkan SK pengangkatan sebagai ASN. "
            "3. Ajukan ke admin IT melalui helpdesk. "
            "4. Email aktif dalam 3 hari kerja. "
            "5. Password awal dikirim ke email pribadi yang didaftarkan."
        ),
    },
    {
        "doc_id": 2,
        "page": 1,
        "text": (
            "SOP reset password akun dinas: "
            "1. Hubungi helpdesk IT di ext. 1234 atau email helpdesk@diskominfotik.go.id. "
            "2. Verifikasi identitas dengan NIP dan nama lengkap. "
            "3. Password sementara dikirim dalam 10 menit. "
            "4. Ganti password sementara segera setelah login. "
            "5. Password harus minimal 8 karakter, kombinasi huruf besar, kecil, dan angka."
        ),
    },
    {
        "doc_id": 2,
        "page": 2,
        "text": (
            "Kebijakan keamanan jaringan: Semua perangkat yang terhubung ke jaringan dinas "
            "wajib menggunakan antivirus yang telah disetujui. "
            "Dilarang menggunakan USB drive pribadi pada komputer dinas. "
            "Akses internet dibatasi sesuai kebutuhan pekerjaan. "
            "Melaporkan insiden keamanan ke tim IT dalam 1 jam setelah terdeteksi."
        ),
    },
    {
        "doc_id": 3,
        "page": 1,
        "text": (
            "Jadwal pemeliharaan sistem: Server utama akan dilakukan maintenance "
            "setiap Sabtu pukul 22.00 - 02.00 WIB. "
            "Selama maintenance, akses ke sistem informasi tidak tersedia. "
            "Notifikasi akan dikirim H-3 sebelum jadwal maintenance. "
            "Untuk keperluan mendesak, hubungi on-call engineer di 0812-3456-7890."
        ),
    },
]

PERTANYAAN_TEST = [
    "Apa syarat untuk mengajukan permohonan server baru?",
    "Bagaimana cara reset password akun dinas?",
    "Kapan jadwal maintenance server?",
]


# ─── Step 1: Test Embedding Model ─────────────────────────────
def test_embedding():
    print("\n" + "=" * 60)
    print("STEP 1: Test Embedding Model")
    print("=" * 60)
    sys.path.insert(0, ".")

    try:
        from app.services.embedding_service import get_embedding_model
        model = get_embedding_model()
        test_text = "Ini adalah teks percobaan untuk embedding"
        embedding = model.encode(test_text)
        print(f"[OK] Model berhasil dimuat")
        print(f"     Dimensi embedding: {len(embedding)}")
        print(f"     Sample teks: '{test_text[:40]}...'")
        return True
    except Exception as e:
        print(f"[GAGAL] {e}")
        return False


# ─── Step 2: Inject Data Sample ke ChromaDB ───────────────────
def inject_sample_data():
    print("\n" + "=" * 60)
    print("STEP 2: Inject Data Sample ke ChromaDB")
    print("=" * 60)

    try:
        from app.services.embedding_service import (
            get_embedding_model,
            get_chroma_collection,
        )

        model = get_embedding_model()
        collection = get_chroma_collection()

        ids, texts, embeddings, metadatas = [], [], [], []

        for i, doc in enumerate(SAMPLE_DOCS):
            chunk_id = f"doc_{doc['doc_id']}_page_{doc['page']}_sample_{i}"
            ids.append(chunk_id)
            texts.append(doc["text"])
            metadatas.append({
                "document_id": doc["doc_id"],
                "page_number": doc["page"],
                "chunk_index": i,
            })

        embeddings = model.encode(texts, show_progress_bar=True).tolist()
        collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

        print(f"\n[OK] {len(ids)} chunk berhasil dimasukkan ke ChromaDB")
        print(f"     Total dokumen di koleksi: {collection.count()}")
        return True
    except Exception as e:
        print(f"[GAGAL] {e}")
        return False


# ─── Step 3: Test Chat via HTTP ───────────────────────────────
# ─── Step 3: Test Chat via HTTP ───────────────────────────────
def test_chat(query: str):
    print(f"\n{'─' * 60}")
    print(f"Pertanyaan: {query}")
    print("─" * 60)
    print("Jawaban AI: ", end="", flush=True)

    try:
        payload = {"session_id": "test-rag-001", "query": query}
        with requests.post(f"{BASE_URL}/api/chat/stream", json=payload, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                print(f"\n[ERROR] Status {resp.status_code}: {resp.text}")
                return False

            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8")

                    # Strip prefix "data: " kalau format SSE
                    if decoded.startswith("data: "):
                        decoded = decoded[len("data: "):]

                    if not decoded.strip():
                        continue

                    try:
                        data = json.loads(decoded)
                        if data["type"] == "chunk":
                            sys.stdout.write(data["content"])
                            sys.stdout.flush()
                        elif data["type"] == "done":
                            print("\n[SELESAI]")
                        elif data["type"] == "error":
                            print(f"\n[ERROR DARI SERVER]: {data['content']}")
                    except json.JSONDecodeError as e:
                        print(f"\n[DEBUG] Gagal parse line: {decoded!r} — {e}")
        return True
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Server tidak bisa dihubungi di port 8000.")
        return False
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False

# ─── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  FULL RAG PIPELINE TEST")
    print("=" * 60)

    # Step 1: Test embedding model
    ok = test_embedding()
    if not ok:
        print("\n[STOP] Embedding model gagal. Cek instalasi sentence-transformers.")
        sys.exit(1)

    # Step 2: Inject data sample
    ok = inject_sample_data()
    if not ok:
        print("\n[STOP] Gagal inject data. Cek ChromaDB.")
        sys.exit(1)

    # Step 3: Test RAG chat
    print("\n" + "=" * 60)
    print("STEP 3: Test RAG Chat (via FastAPI)")
    print("=" * 60)

    all_ok = True
    for q in PERTANYAAN_TEST:
        ok = test_chat(q)
        if not ok:
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("SEMUA TEST BERHASIL!")
    else:
        print("ADA TEST YANG GAGAL. Periksa log di atas.")
    print("=" * 60)
