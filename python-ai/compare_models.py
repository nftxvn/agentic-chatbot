"""
Perbandingan kualitas RAG antar model LLM (mis. qwen2.5:7b vs qwen3.5:4b).

Menjalankan subset pertanyaan dari reference_eval_dataset.json melalui pipeline
RAG penuh, lalu menilainya dengan metrik yang sama seperti test_ragas_eval.py.
Hasil tiap model disimpan ke JSON terpisah supaya bisa dibandingkan.

Model DIPILIH lewat environment variable LLM_MODEL_NAME (bukan argumen), karena
app/config.py membaca nilai itu dan load_dotenv() tidak menimpa env var yang
sudah ada. Jalankan satu proses per model agar tidak ada state model yang
tercampur di memori.

Cara pakai (PowerShell):
    $env:LLM_MODEL_NAME = 'qwen2.5:7b'; python compare_models.py
    $env:LLM_MODEL_NAME = 'qwen3.5:4b'; python compare_models.py

Lalu bandingkan:
    python compare_models.py --report
"""

import os
import sys
import json
import time
import glob
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Subset pertanyaan untuk perbandingan.
# Dipilih yang ground_truth-nya PENDEK supaya jumlah klaim (= jumlah panggilan
# LLM verifikasi) tetap wajar, tapi tetap mewakili berbagai kategori —
# termasuk 2 pertanyaan jebakan (q05 diktum KETIGA, q25 kualifikasi Renja).
SUBSET_IDS = ["q05", "q07", "q09", "q18", "q22", "q25"]

RESULT_PREFIX = "compare_result_"


def _slug(model_name: str) -> str:
    return model_name.replace(":", "_").replace("/", "_").replace(".", "-")


def run_for_current_model():
    """Jalankan evaluasi subset untuk model yang aktif di settings.LLM_MODEL_NAME."""
    # Import ditunda sampai di sini agar env var LLM_MODEL_NAME sudah terpasang
    # sebelum app.config dimuat.
    from app.config import settings
    import test_ragas_eval as ev

    model = settings.LLM_MODEL_NAME
    print("\n" + "=" * 60)
    print(f"  PERBANDINGAN MODEL — {model}")
    print(f"  Subset: {', '.join(SUBSET_IDS)}")
    print("=" * 60)

    dataset = ev.load_reference_dataset()
    subset = [d for d in dataset if d["id"] in SUBSET_IDS]
    missing = set(SUBSET_IDS) - {d["id"] for d in subset}
    if missing:
        logger.warning(f"ID tidak ditemukan di dataset: {sorted(missing)}")

    # Waktu generasi dan waktu penilaian dicatat terpisah: penilaian memakai model
    # juri yang sama untuk semua kandidat, jadi hanya waktu GENERASI yang absah
    # dipakai membandingkan kecepatan antar model.
    started = time.time()
    rag_data = ev.collect_rag_data(subset)
    gen_elapsed = time.time() - started

    judge_started = time.time()
    evaluated = ev.run_evaluation(rag_data)
    judge_elapsed = time.time() - judge_started
    elapsed = time.time() - started

    summary = {
        "model": model,
        "judge_model": ev.EVAL_MODEL,
        "elapsed_seconds": round(elapsed, 1),
        "generation_seconds": round(gen_elapsed, 1),
        "judging_seconds": round(judge_elapsed, 1),
        "n_questions": len(evaluated),
        "avg_faithfulness": ev._avg([r["faithfulness"] for r in evaluated]),
        "avg_answer_relevancy": ev._avg([r["answer_relevancy"] for r in evaluated]),
        "avg_context_recall": ev._avg([r["context_recall"] for r in evaluated]),
        "avg_answer_correctness": ev._avg([r["answer_correctness"] for r in evaluated]),
        "per_question": [
            {
                "id": r["id"],
                "category": r["category"],
                "question": r["question"],
                "answer": r["answer"],
                # Konteks ikut disimpan supaya penilaian ulang dengan juri lain
                # tidak perlu menjalankan ulang pipeline RAG yang mahal.
                "contexts": r["contexts"],
                "faithfulness": r["faithfulness"],
                "answer_relevancy": r["answer_relevancy"],
                "context_recall": r["context_recall"],
                "answer_correctness": r["answer_correctness"],
            }
            for r in evaluated
        ],
    }

    out_path = f"{RESULT_PREFIX}{_slug(model)}__judge_{_slug(ev.EVAL_MODEL)}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"  SELESAI — {model}  ({elapsed/60:.1f} menit)")
    print(f"  Faithfulness       : {ev._fmt(summary['avg_faithfulness'])}")
    print(f"  Answer Relevancy   : {ev._fmt(summary['avg_answer_relevancy'])}")
    print(f"  Context Recall     : {ev._fmt(summary['avg_context_recall'])}")
    print(f"  Answer Correctness : {ev._fmt(summary['avg_answer_correctness'])}")
    print(f"  Disimpan ke: {out_path}")
    print("=" * 60)
    return summary


def _fmt(v):
    return f"{v:.4f}" if isinstance(v, (int, float)) else "N/A"


def build_report():
    """Bandingkan semua compare_result_*.json yang ada dan tulis laporan markdown."""
    files = sorted(glob.glob(f"{RESULT_PREFIX}*.json"))
    if len(files) < 2:
        print(f"Butuh minimal 2 hasil untuk dibandingkan, baru ada {len(files)}: {files}")
        print("Jalankan dulu evaluasi untuk tiap model (lihat docstring).")
        return

    results = []
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            results.append(json.load(f))

    out_path = "hasil_perbandingan_model.md"
    metrics = [
        ("avg_faithfulness", "Faithfulness"),
        ("avg_answer_relevancy", "Answer Relevancy"),
        ("avg_context_recall", "Context Recall"),
        ("avg_answer_correctness", "Answer Correctness"),
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Perbandingan Model LLM untuk RAG SOP\n\n")
        f.write(f"> Subset {results[0]['n_questions']} pertanyaan: `{', '.join(SUBSET_IDS)}`\n")
        f.write("> Ground truth: `reference_eval_dataset.json`\n")
        judges = {r.get("judge_model", "?") for r in results}
        f.write(f"> Model juri: `{', '.join(sorted(judges))}`")
        if len(judges) > 1:
            f.write("  ⚠️ **JURI BERBEDA — perbandingan TIDAK sah**")
        f.write("\n\n")

        f.write("## Ringkasan\n\n")
        f.write("| Metrik | " + " | ".join(r["model"] for r in results) + " |\n")
        f.write("|--------|" + "|".join(["------"] * len(results)) + "|\n")
        for key, label in metrics:
            f.write(f"| {label} | " + " | ".join(f"`{_fmt(r[key])}`" for r in results) + " |\n")
        f.write("| **Waktu GENERASI** (menit) | " + " | ".join(
            f"`{r.get('generation_seconds', 0)/60:.1f}`" for r in results) + " |\n")
        f.write("| Waktu penilaian (menit) | " + " | ".join(
            f"`{r.get('judging_seconds', 0)/60:.1f}`" for r in results) + " |\n\n")
        f.write("> Hanya **waktu generasi** yang absah dipakai membandingkan kecepatan model — "
                "waktu penilaian ditentukan oleh model juri yang sama untuk semua kandidat.\n\n")

        f.write("## Detail per Pertanyaan\n\n")
        by_id = {}
        for r in results:
            for q in r["per_question"]:
                by_id.setdefault(q["id"], {})[r["model"]] = q

        for qid in SUBSET_IDS:
            if qid not in by_id:
                continue
            entries = by_id[qid]
            first = next(iter(entries.values()))
            f.write(f"### {qid} — {first['category']}\n\n")
            f.write(f"**Q:** {first['question']}\n\n")
            f.write("| Model | Faithfulness | Ans. Relevancy | Ctx Recall | Ans. Correctness |\n")
            f.write("|-------|--------------|----------------|------------|------------------|\n")
            for model, q in entries.items():
                f.write(
                    f"| {model} | `{_fmt(q['faithfulness'])}` | `{_fmt(q['answer_relevancy'])}` "
                    f"| `{_fmt(q['context_recall'])}` | `{_fmt(q['answer_correctness'])}` |\n"
                )
            f.write("\n")
            for model, q in entries.items():
                f.write(f"<details><summary>Jawaban {model}</summary>\n\n{q['answer']}\n\n</details>\n\n")
            f.write("---\n\n")

    print(f"\n[OK] Laporan perbandingan disimpan ke: {out_path}")
    for r in results:
        print(f"  {r['model']:20s} correctness={_fmt(r['avg_answer_correctness'])} "
              f"faithfulness={_fmt(r['avg_faithfulness'])} ({r['elapsed_seconds']/60:.1f} menit)")


if __name__ == "__main__":
    if "--report" in sys.argv:
        build_report()
    else:
        if not os.getenv("LLM_MODEL_NAME"):
            print("PERINGATAN: env var LLM_MODEL_NAME tidak diset — memakai nilai dari .env")
        run_for_current_model()
