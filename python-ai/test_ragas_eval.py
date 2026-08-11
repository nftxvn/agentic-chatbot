"""
Evaluasi RAG pipeline menggunakan metrik Ragas-equivalent secara manual.
Metrik yang dievaluasi:
  - Faithfulness       : apakah jawaban berasal dari konteks yang di-retrieve?
  - Answer Relevancy   : apakah jawaban relevan terhadap pertanyaan?
  - Context Recall     : apakah konteks yang di-retrieve mencakup fakta-fakta
                          di jawaban referensi (ground_truth)? (butuh ground truth)
  - Answer Correctness : seberapa sesuai jawaban RAG dengan jawaban referensi
                          (ground_truth)? (butuh ground truth)

Ground truth diambil dari reference_eval_dataset.json (dataset referensi yang
ditulis & diverifikasi manual dari dokumen sumber — lihat reference_eval_dataset.md).

Tidak memerlukan `ragas` library sehingga bebas konflik versi langchain.
LLM Evaluator: Ollama (model yang sama dengan RAG pipeline).

Cara pakai:
    python test_ragas_eval.py
"""

import os
import sys
import json
import logging
import requests
from collections import defaultdict
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from app.config import settings
from app.services.rag_service import _retrieve_context, generate_response, _correct_query_typos

# ──────────────────────────────────────────────────────
# Konfigurasi
# ──────────────────────────────────────────────────────
OLLAMA_URL     = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/generate"

# Model JURI (yang menilai), sengaja dipisah dari model GENERASI (LLM_MODEL_NAME).
# Kalau keduanya disamakan, tiap model menilai jawabannya sendiri — yang terukur
# jadi "kualitas RAG x kelonggaran juri", bukan kualitas RAG. Model yang jurinya
# lebih ketat akan menghukum dirinya sendiri, sehingga perbandingan antar model
# tidak sah. Set RAGAS_EVAL_MODEL ke satu model tetap saat membandingkan.
EVAL_MODEL     = os.getenv("RAGAS_EVAL_MODEL", settings.LLM_MODEL_NAME)
SESSION_ID     = "ragas-eval"
REFERENCE_PATH = "reference_eval_dataset.json"

# Batas jumlah klaim yang diverifikasi per metrik. Tanpa ini, pertanyaan dengan
# jawaban panjang (mis. q04 = daftar 74 SOP) menghasilkan puluhan klaim, dan tiap
# klaim butuh 1 panggilan LLM tersendiri untuk verifikasi — evaluasi jadi tidak
# selesai-selesai. Klaim diambil dari urutan awal (paling representatif).
_MAX_CLAIMS = int(os.getenv("RAGAS_MAX_CLAIMS", "12"))


# ──────────────────────────────────────────────────────
# Dataset Referensi (Ground Truth)
# ──────────────────────────────────────────────────────
def load_reference_dataset(path: str = REFERENCE_PATH) -> List[Dict]:
    """Muat dataset ground truth (question + ground_truth + category + notes)."""
    with open(path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    logger.info(f"Dataset referensi dimuat: {len(dataset)} pertanyaan dari {path}")
    return dataset


# ──────────────────────────────────────────────────────
# Helper: Panggil Ollama Langsung
# ──────────────────────────────────────────────────────
def call_ollama(prompt: str, temperature: float = 0.0) -> str:
    """Panggil Ollama REST API dan kembalikan teks responsnya."""
    payload = {
        "model": EVAL_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
        # Matikan mode thinking. Pada model seperti qwen3.5, thinking aktif secara
        # default dan seluruh anggaran token habis untuk penalaran internal —
        # field "response" pulang KOSONG sehingga semua metrik jadi 0.
        # Aman untuk model tanpa thinking (mis. qwen2.5), Ollama mengabaikannya.
        "think": False,
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Gagal memanggil Ollama: {e}")
        return ""


# ──────────────────────────────────────────────────────
# Helper Bersama: Ekstraksi & Verifikasi Klaim (LLM-judge)
# ──────────────────────────────────────────────────────
def _extract_claims(text: str, label: str = "jawaban") -> List[str]:
    """Ekstrak setiap klaim faktual dari sebuah teks menggunakan LLM."""
    prompt = f"""Kamu adalah penilai klaim.
Diberikan {label} berikut, ekstrak SETIAP klaim faktual yang ada.
Kembalikan daftar klaim, satu per baris, diawali dengan nomor (1. 2. 3. ...).
Jika tidak ada klaim, tulis "tidak ada klaim".

{label.upper()}:
{text}

KLAIM:"""
    raw = call_ollama(prompt)
    if not raw or "tidak ada klaim" in raw.lower():
        return []
    claims = [
        line.strip().lstrip("0123456789. ").strip()
        for line in raw.splitlines()
        if line.strip() and line.strip()[0].isdigit()
    ]
    if len(claims) > _MAX_CLAIMS:
        logger.info(f"  ({len(claims)} klaim diekstrak, dibatasi ke {_MAX_CLAIMS} teratas)")
        claims = claims[:_MAX_CLAIMS]
    return claims


def _claim_supported(claim: str, source_text: str) -> bool:
    """Cek apakah sebuah klaim DIDUKUNG SEPENUHNYA oleh source_text (LLM judge Ya/Tidak)."""
    prompt = f"""Kamu adalah penilai akurasi.
Apakah klaim berikut DIDUKUNG SEPENUHNYA oleh sumber yang diberikan?
Jawab HANYA dengan "Ya" atau "Tidak".

SUMBER:
{source_text}

KLAIM:
{claim}

JAWABAN (Ya/Tidak):"""
    verdict = call_ollama(prompt).strip().lower()
    return verdict.startswith("ya") or verdict.startswith("yes")


# ──────────────────────────────────────────────────────
# Helper Bersama: Model Embedding (singleton, dipakai lintas metrik)
# ──────────────────────────────────────────────────────
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Memuat model embedding untuk evaluasi: {settings.EMBEDDING_MODEL_NAME} ...")
        _embed_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _embed_model


def _cosine_similarity(text_a: str, text_b: str) -> float:
    import numpy as np
    model = _get_embed_model()
    emb = model.encode([text_a, text_b])
    a_norm = emb[0] / (np.linalg.norm(emb[0]) + 1e-9)
    b_norm = emb[1] / (np.linalg.norm(emb[1]) + 1e-9)
    return float(np.dot(a_norm, b_norm))


# ──────────────────────────────────────────────────────
# Metrik 1: Faithfulness (butuh: answer, contexts — TIDAK butuh ground truth)
# ──────────────────────────────────────────────────────
def evaluate_faithfulness(question: str, answer: str, contexts: List[str]) -> float:
    """
    Mengukur apakah setiap klaim dalam jawaban dapat didukung oleh konteks yang di-retrieve.
    Nilai: 0.0 (tidak ada klaim yang didukung) – 1.0 (semua klaim didukung).
    """
    context_text = "\n\n".join(contexts) if contexts else "(tidak ada konteks)"

    claims = _extract_claims(answer, label="jawaban")
    if not claims:
        return 1.0  # Jawaban kosong atau tidak ada klaim = tidak ada yang bisa dibantah

    supported = sum(1 for c in claims if _claim_supported(c, context_text))
    score = supported / len(claims)
    logger.info(f"  Faithfulness: {supported}/{len(claims)} klaim didukung = {score:.2f}")
    return round(score, 4)


# ──────────────────────────────────────────────────────
# Metrik 2: Answer Relevancy (butuh: question, answer — TIDAK butuh ground truth)
# ──────────────────────────────────────────────────────
def evaluate_answer_relevancy(question: str, answer: str, n: int = 3) -> float:
    """
    Mengukur seberapa relevan jawaban terhadap pertanyaan.
    Caranya: LLM diminta membuat N pertanyaan balik dari jawaban,
    lalu kita cek similarity dengan pertanyaan asli menggunakan embedding kosinus.
    Nilai: 0.0 (tidak relevan) – 1.0 (sangat relevan).
    """
    if not answer or len(answer.strip()) < 10:
        return 0.0

    gen_prompt = f"""Diberikan jawaban berikut, buatlah {n} pertanyaan berbeda yang PALING TEPAT dijawab oleh jawaban tersebut.
Satu pertanyaan per baris, tanpa penomoran, tanpa penjelasan.

JAWABAN:
{answer}

PERTANYAAN:"""
    questions_raw = call_ollama(gen_prompt)
    generated_qs = [
        q.strip()
        for q in questions_raw.splitlines()
        if q.strip() and not q.strip().startswith("#")
    ][:n]

    if not generated_qs:
        return 0.0

    try:
        scores = [max(0.0, _cosine_similarity(question, gq)) for gq in generated_qs]
        avg_score = sum(scores) / len(scores)
        logger.info(f"  Answer Relevancy: {len(scores)} generated questions, avg similarity = {avg_score:.2f}")
        return round(avg_score, 4)
    except Exception as e:
        logger.warning(f"  Gagal hitung similarity ({e}), fallback ke LLM scoring...")
        rel_prompt = f"""Seberapa relevan jawaban ini terhadap pertanyaan?
Berikan skor dari 0.0 hingga 1.0.
Kembalikan HANYA angka desimal, tanpa penjelasan.

PERTANYAAN: {question}
JAWABAN: {answer}

SKOR:"""
        try:
            score_str = call_ollama(rel_prompt).strip().replace(",", ".")
            return round(float(score_str), 4)
        except Exception:
            return 0.5


# ──────────────────────────────────────────────────────
# Metrik 3: Context Recall (butuh: contexts, ground_truth)
# ──────────────────────────────────────────────────────
def evaluate_context_recall(contexts: List[str], ground_truth: str) -> Optional[float]:
    """
    Mengukur seberapa lengkap konteks yang di-retrieve RAG mencakup fakta-fakta
    yang ada di ground_truth (jawaban referensi). Nilai rendah = kegagalan RETRIEVAL,
    terlepas dari bagus/tidaknya generation LLM.
    Nilai: 0.0 (tidak ada fakta ground truth yang ditemukan) – 1.0 (semua ditemukan).
    Return None jika tidak ada ground_truth untuk dibandingkan.
    """
    if not ground_truth:
        return None
    context_text = "\n\n".join(contexts) if contexts else "(tidak ada konteks)"

    facts = _extract_claims(ground_truth, label="jawaban referensi")
    if not facts:
        return 1.0

    found = sum(1 for f in facts if _claim_supported(f, context_text))
    score = found / len(facts)
    logger.info(f"  Context Recall: {found}/{len(facts)} fakta referensi ditemukan di konteks = {score:.2f}")
    return round(score, 4)


# ──────────────────────────────────────────────────────
# Metrik 4: Answer Correctness (butuh: answer, ground_truth)
# ──────────────────────────────────────────────────────
def evaluate_answer_correctness(answer: str, ground_truth: str) -> Optional[float]:
    """
    Mengukur kesesuaian jawaban RAG terhadap jawaban referensi (ground_truth),
    kombinasi dari:
      - Factual recall     : % fakta di ground_truth yang tercakup di jawaban RAG
      - Semantic similarity: cosine similarity embedding jawaban RAG vs ground_truth
    Nilai: 0.0 (tidak sesuai sama sekali) – 1.0 (sepenuhnya sesuai).
    Return None jika tidak ada ground_truth untuk dibandingkan.
    """
    if not ground_truth:
        return None
    if not answer or len(answer.strip()) < 3:
        return 0.0

    facts = _extract_claims(ground_truth, label="jawaban referensi")
    if facts:
        matched = sum(1 for f in facts if _claim_supported(f, answer))
        factual_recall = matched / len(facts)
    else:
        factual_recall = 1.0

    try:
        semantic_sim = max(0.0, _cosine_similarity(answer, ground_truth))
    except Exception as e:
        logger.warning(f"  Gagal hitung semantic similarity ({e}), pakai factual_recall saja")
        semantic_sim = factual_recall

    score = round((factual_recall + semantic_sim) / 2, 4)
    logger.info(
        f"  Answer Correctness: factual_recall={factual_recall:.2f}, "
        f"semantic_sim={semantic_sim:.2f} -> {score:.2f}"
    )
    return score


# ──────────────────────────────────────────────────────
# Pengumpulan Data dari RAG Pipeline
# ──────────────────────────────────────────────────────
def collect_rag_data(dataset: List[Dict]) -> List[Dict]:
    """Jalankan setiap entri dataset referensi ke RAG pipeline dan kumpulkan hasilnya."""
    results = []
    total = len(dataset)

    for i, item in enumerate(dataset, start=1):
        q = item["question"]
        logger.info(f"\n[{i}/{total}] ({item.get('id', '?')}) Memproses: {q}")

        # Ambil konteks
        corrected_q = _correct_query_typos(q)
        context_text, _ = _retrieve_context(corrected_q, original_query=q)
        contexts = (
            [c.strip() for c in context_text.split("\n\n---\n\n") if c.strip()]
            if context_text else []
        )

        # Ambil jawaban
        chunks = []
        try:
            for chunk in generate_response(q, SESSION_ID):
                chunks.append(chunk)
        except Exception as e:
            logger.error(f"  Gagal generate jawaban: {e}")
        answer = "".join(chunks)
        # Hilangkan bagian sumber referensi
        if "📚 **Sumber Referensi:**" in answer:
            answer = answer.split("📚 **Sumber Referensi:**")[0].strip()

        logger.info(f"  Konteks diambil: {len(contexts)} chunk")
        logger.info(f"  Jawaban ({len(answer)} karakter): {answer[:100]}...")

        results.append({
            "id": item.get("id", f"q{i:02d}"),
            "category": item.get("category", "-"),
            "question": q,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": item.get("ground_truth", ""),
            "notes": item.get("notes"),
        })

    return results


# ──────────────────────────────────────────────────────
# Evaluasi Ragas-Equivalent
# ──────────────────────────────────────────────────────
def run_evaluation(data: List[Dict]) -> List[Dict]:
    """Evaluasi setiap item dengan metrik faithfulness, answer_relevancy,
    context_recall, dan answer_correctness."""
    evaluated = []

    for i, item in enumerate(data, start=1):
        q            = item["question"]
        ans          = item["answer"]
        contexts     = item["contexts"]
        ground_truth = item.get("ground_truth", "")

        logger.info(f"\n─── Evaluasi [{i}/{len(data)}] ({item.get('id', '?')}) ───")
        logger.info(f"  Q: {q}")

        faith = evaluate_faithfulness(q, ans, contexts)
        relev = evaluate_answer_relevancy(q, ans)
        recall = evaluate_context_recall(contexts, ground_truth)
        correctness = evaluate_answer_correctness(ans, ground_truth)

        evaluated.append({
            **item,
            "faithfulness": faith,
            "answer_relevancy": relev,
            "context_recall": recall,
            "answer_correctness": correctness,
        })
        logger.info(
            f"  ✓ faithfulness={faith:.4f}, answer_relevancy={relev:.4f}, "
            f"context_recall={_fmt(recall)}, answer_correctness={_fmt(correctness)}"
        )

    return evaluated


def _fmt(value: Optional[float]) -> str:
    return f"{value:.4f}" if value is not None else "N/A"


def _avg(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


# ──────────────────────────────────────────────────────
# Simpan Laporan
# ──────────────────────────────────────────────────────
def save_report(evaluated: List[Dict]):
    output_path = "hasil_ragas_eval.md"

    avg_faith       = _avg([r["faithfulness"] for r in evaluated])
    avg_relev       = _avg([r["answer_relevancy"] for r in evaluated])
    avg_recall      = _avg([r["context_recall"] for r in evaluated])
    avg_correctness = _avg([r["answer_correctness"] for r in evaluated])

    # Rekap per kategori
    by_category: Dict[str, List[Dict]] = defaultdict(list)
    for r in evaluated:
        by_category[r.get("category", "-")].append(r)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Laporan Evaluasi RAG — Metrik Ragas-Equivalent\n\n")
        f.write("> Evaluasi menggunakan Ollama lokal sebagai LLM evaluator.\n")
        f.write(f"> Model: `{EVAL_MODEL}` · Embedding: `{settings.EMBEDDING_MODEL_NAME}`\n")
        f.write(f"> Ground truth: `{REFERENCE_PATH}` ({len(evaluated)} pertanyaan)\n\n")

        f.write("## Ringkasan Skor\n\n")
        f.write("| Metrik | Skor | Butuh Ground Truth? |\n")
        f.write("|--------|------|----------------------|\n")
        f.write(f"| **Faithfulness** (rata-rata) | `{_fmt(avg_faith)}` | Tidak |\n")
        f.write(f"| **Answer Relevancy** (rata-rata) | `{_fmt(avg_relev)}` | Tidak |\n")
        f.write(f"| **Context Recall** (rata-rata) | `{_fmt(avg_recall)}` | Ya |\n")
        f.write(f"| **Answer Correctness** (rata-rata) | `{_fmt(avg_correctness)}` | Ya |\n\n")

        f.write("## Rekap per Kategori\n\n")
        f.write("| Kategori | N | Faithfulness | Answer Relevancy | Context Recall | Answer Correctness |\n")
        f.write("|----------|---|--------------|-------------------|-----------------|---------------------|\n")
        for cat in sorted(by_category.keys()):
            rows = by_category[cat]
            f.write(
                f"| {cat} | {len(rows)} "
                f"| `{_fmt(_avg([r['faithfulness'] for r in rows]))}` "
                f"| `{_fmt(_avg([r['answer_relevancy'] for r in rows]))}` "
                f"| `{_fmt(_avg([r['context_recall'] for r in rows]))}` "
                f"| `{_fmt(_avg([r['answer_correctness'] for r in rows]))}` |\n"
            )
        f.write("\n---\n\n## Detail per Pertanyaan\n\n")

        for i, r in enumerate(evaluated, start=1):
            f.write(f"### {r.get('id', f'q{i:02d}')} — {r.get('category', '-')}\n\n")
            f.write(f"**Q:** {r['question']}\n\n")
            f.write(f"**A (RAG):** {r['answer']}\n\n")
            if r.get("ground_truth"):
                f.write(f"**Ground Truth:** {r['ground_truth']}\n\n")
            if r.get("notes"):
                f.write(f"> **Catatan:** {r['notes']}\n\n")
            f.write("| Metrik | Skor |\n")
            f.write("|--------|------|\n")
            f.write(f"| Faithfulness | `{r['faithfulness']:.4f}` |\n")
            f.write(f"| Answer Relevancy | `{r['answer_relevancy']:.4f}` |\n")
            f.write(f"| Context Recall | `{_fmt(r['context_recall'])}` |\n")
            f.write(f"| Answer Correctness | `{_fmt(r['answer_correctness'])}` |\n\n")
            f.write("---\n\n")

    logger.info(f"\n✅ Laporan disimpan ke: {output_path}")
    return avg_faith, avg_relev, avg_recall, avg_correctness


# ──────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RAG EVALUATION — Ragas-Equivalent Metrics (+ Ground Truth)")
    print("  Model LLM  :", EVAL_MODEL)
    print("  Ollama URL :", OLLAMA_URL)
    print("=" * 60)

    # Fase 0: Muat dataset referensi (ground truth)
    print("\n[FASE 0] Memuat dataset referensi...")
    dataset = load_reference_dataset()

    # Fase 1: Kumpulkan data RAG
    print(f"\n[FASE 1] Mengumpulkan data dari RAG pipeline ({len(dataset)} pertanyaan)...")
    rag_data = collect_rag_data(dataset)

    # Fase 2: Evaluasi
    print("\n[FASE 2] Menjalankan evaluasi metrik...")
    evaluated = run_evaluation(rag_data)

    # Fase 3: Simpan laporan
    print("\n[FASE 3] Menyimpan laporan...")
    avg_faith, avg_relev, avg_recall, avg_correctness = save_report(evaluated)

    print("\n" + "=" * 60)
    print("  HASIL AKHIR")
    print(f"  Faithfulness (avg)        : {_fmt(avg_faith)}")
    print(f"  Answer Relevancy (avg)    : {_fmt(avg_relev)}")
    print(f"  Context Recall (avg)      : {_fmt(avg_recall)}")
    print(f"  Answer Correctness (avg)  : {_fmt(avg_correctness)}")
    print("=" * 60)
