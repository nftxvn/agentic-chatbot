"""
Evaluasi RAG memakai library RAGAS resmi (bukan implementasi manual).

Bedanya dengan test_ragas_eval.py:
  - test_ragas_eval.py  : metrik ditulis sendiri, tanpa dependensi ragas.
  - file ini            : memakai library `ragas` asli, sehingga metriknya
                          sebanding dengan hasil publikasi/paper orang lain.

Metrik yang dijalankan (empat terakhir butuh ground truth):
  - Faithfulness                     : klaim jawaban didukung konteks?
  - ResponseRelevancy                : jawaban relevan dengan pertanyaan?
  - LLMContextRecall                 : konteks memuat fakta jawaban referensi?
  - LLMContextPrecisionWithReference : konteks yang diambil memang berguna?
  - FactualCorrectness               : fakta jawaban cocok dengan referensi?

Semua berjalan lokal lewat Ollama — tidak ada data yang dikirim ke layanan luar.

Cara pakai:
    python test_ragas_official.py --gemini --limit 3  # juri Gemini (cepat)
    python test_ragas_official.py --limit 2 --fast    # juri lokal, paling ringan
    python test_ragas_official.py --limit 3           # 3 pertanyaan, 5 metrik
    python test_ragas_official.py --ids q05,q07       # pertanyaan tertentu
    python test_ragas_official.py --metrics faithfulness,factual_correctness
    python test_ragas_official.py --all               # 26 pertanyaan (sangat lama)

Pemilihan juri:
    --gemini   juri di server Google (butuh GEMINI_API_KEY di .env)
    --ollama   juri lokal (bawaan)
    Keduanya menang atas env var RAGAS_JUDGE_PROVIDER.

    --judge-model=<nama>  ganti model Gemini (mis. gemini-3.5-flash-lite)
    --list-models         daftar model yang boleh dipakai API key ini
    --reuse               pakai jawaban RAG dari run sebelumnya (lewati fase 1)
    --verbose             tampilkan seluruh log (retrieval, embedding, HTTP)

Keluaran bawaan sengaja ringkas: banner TensorFlow, peringatan deprecation,
telemetri ChromaDB, dan bilah kemajuan embedding disembunyikan karena tidak
menjelaskan apa pun tentang HASIL evaluasi. Kegagalan sungguhan tetap tampil.
Untuk membedah masalah retrieval, jalankan ulang dengan --verbose.

Mengulang penilaian tanpa menunggu lama:
    Fase 1 (Ollama menjawab) makan waktu menit per pertanyaan, sedangkan fase 2
    (juri menilai) bisa gagal karena jatah habis. Hasil fase 1 selalu disimpan
    ke .ragas_cache_phase1.json, jadi percobaan berikutnya cukup:
        python test_ragas_official.py --gemini --limit 3 --reuse
    Cache hanya dipakai bila pertanyaan dan model generasinya sama persis.

Jatah gratis Gemini — sering jadi penyebab skor nan:
    Jatah dihitung PER MODEL PER HARI, dan model flagship terbaru justru
    berjatah paling sempit (gemini-3.6-flash: 20 permintaan/hari). Metrik
    context_precision mengirim SATU permintaan untuk SETIAP potongan konteks,
    jadi 3 pertanyaan bertipe daftar saja bisa menghabiskan 60 permintaan.
    Kalau kena 429: pindah model dengan --judge-model (jatah baru seketika)
    atau pakai --fast yang melewati metrik boros itu.

Catatan waktu — penting di mesin tanpa GPU memadai:
    Metrik faithfulness, context_recall, dan context_precision masing-masing
    mengirim SELURUH konteks hasil retrieval (~3.600 token rata-rata pada
    dokumen ini) ke prompt juri. Satu panggilan bisa 2-5 menit bila model
    sebagian jalan di CPU. Pakai --fast untuk melewati ketiganya.
"""

import os
import sys

# ──────────────────────────────────────────────────────────────────
# Mode senyap — HARUS dipasang sebelum library berat diimpor
# ──────────────────────────────────────────────────────────────────
# Tanpa ini, keluaran evaluasi tenggelam di ratusan baris yang tidak ada
# hubungannya dengan hasil: banner TensorFlow, peringatan deprecation
# langchain/ragas, kegagalan telemetri ChromaDB, dan bilah kemajuan embedding.
#
# TF_CPP_MIN_LOG_LEVEL dan ANONYMIZED_TELEMETRY dibaca library YANG BERSANGKUTAN
# saat diimpor, jadi memasangnya setelah baris `import` tidak berpengaruh apa pun.
# Itulah alasan blok ini berada di paling atas, mendahului import lainnya.
VERBOSE = "--verbose" in sys.argv

# Kemajuan fase dicetak ke stdout (ditahan di buffer), sedangkan log menulis ke
# stderr (langsung). Akibatnya keduanya muncul tidak sesuai urutan kejadian —
# mis. "Laporan disimpan" tampil sebelum "[FASE 3]". Menyalakan line buffering
# membuat tiap baris stdout langsung keluar, sehingga urutannya kembali benar.
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:  # Python < 3.7
    pass

if not VERBOSE:
    import warnings

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")     # banner oneDNN/absl
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # telemetri ChromaDB
    os.environ.setdefault("CHROMA_TELEMETRY_ENABLED", "False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

import json  # noqa: E402
import types  # noqa: E402
import logging  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Logger yang membanjiri layar tanpa menambah informasi soal HASIL evaluasi.
# Semuanya diturunkan ke ERROR, jadi kegagalan sungguhan (mis. 429 dari Gemini)
# tetap terlihat — yang hilang hanya derap langkahnya.
#
# Catatan: logger test_ragas_eval SENGAJA dibiarkan INFO. Dari sanalah kemajuan
# per pertanyaan dicetak ("[1/3] (q01) Memproses: ..."), dan pada fase 1 yang
# makan waktu menit, tanpa itu layar terlihat menggantung tanpa kabar.
_QUIET_LOGGERS = (
    "LiteLLM", "litellm", "httpx", "httpcore", "urllib3",   # klien HTTP juri
    "chromadb", "chromadb.telemetry", "posthog",            # telemetri vector DB
    "sentence_transformers", "transformers", "datasets",    # pemuatan model
    "app.services.rag_service", "app.services.embedding_service",
    "tensorflow", "absl", "h5py", "numexpr",
)
for _noisy in _QUIET_LOGGERS:
    logging.getLogger(_noisy).setLevel(logging.ERROR if not VERBOSE else logging.INFO)


# ──────────────────────────────────────────────────────────────────
# Shim kompatibilitas — WAJIB dijalankan sebelum `import ragas`
# ──────────────────────────────────────────────────────────────────
def _patch_langchain_community_vertexai() -> None:
    """
    ragas 0.4.3 mengimpor `langchain_community.chat_models.vertexai`, modul yang
    sudah dihapus dari langchain-community 0.4.x (paket itu sedang di-sunset).
    Tanpa penambal ini, `import ragas` gagal dengan ModuleNotFoundError.

    Aman dilakukan: di dalam ragas, ChatVertexAI dan VertexAI HANYA dipakai
    sebagai anggota daftar MULTIPLE_COMPLETION_SUPPORTED yang dicek dengan
    isinstance() (ragas/llms/base.py). Karena kita memakai ChatOllama — yang
    memang bukan salah satu dari keduanya — hasil pengecekan tetap False,
    persis seperti bila modul aslinya ada.

    Penambalan ini hanya berlaku di dalam proses evaluasi; dependensi aplikasi
    tidak disentuh sama sekali (app/ tidak memakai langchain_community).
    """
    import langchain_community.chat_models as chat_models

    if "langchain_community.chat_models.vertexai" not in sys.modules:
        stub = types.ModuleType("langchain_community.chat_models.vertexai")

        class ChatVertexAI:  # hanya penanda tipe, tidak pernah diinstansiasi
            pass

        stub.ChatVertexAI = ChatVertexAI
        sys.modules["langchain_community.chat_models.vertexai"] = stub
        chat_models.vertexai = stub

    import langchain_community.llms as llms

    if not hasattr(llms, "VertexAI"):
        class VertexAI:  # idem
            pass

        llms.VertexAI = VertexAI


_patch_langchain_community_vertexai()

from langchain_core.embeddings import Embeddings
from langchain_ollama import ChatOllama

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
from ragas.metrics import (
    Faithfulness,
    FactualCorrectness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

from app.config import settings
from test_ragas_eval import collect_rag_data, load_reference_dataset

# ──────────────────────────────────────────────────────────────────
# Konfigurasi
# ──────────────────────────────────────────────────────────────────
# Model JURI dipisah dari model generasi. Kalau disamakan, model menilai
# jawabannya sendiri dan skornya mencerminkan kelonggaran juri, bukan kualitas
# RAG — perbandingan antar model jadi tidak sah.
JUDGE_MODEL = os.getenv("RAGAS_EVAL_MODEL", settings.LLM_MODEL_NAME)
OUTPUT_PATH = "hasil_ragas_official.md"
DEFAULT_LIMIT = 6

# ── Pilihan juri ─────────────────────────────────────────────────
# "ollama" (bawaan) : juri lokal, tidak ada data yang keluar dari mesin.
# "gemini"          : juri independen di server Google. Menghilangkan masalah
#                     model menilai jawabannya sendiri, TAPI pertanyaan,
#                     jawaban, dan SELURUH isi konteks dokumen dikirim ke
#                     Google. Untuk dokumen internal instansi, pastikan ini
#                     memang diizinkan.
JUDGE_PROVIDER = os.getenv("RAGAS_JUDGE_PROVIDER", "ollama").lower()

# Flag --gemini / --ollama di baris perintah menang atas env var. Env var di
# PowerShell hanya berlaku pada jendela terminal yang sama dan gampang lupa
# diketik — akibatnya evaluasi diam-diam memakai juri lokal yang lambat.
if "--gemini" in sys.argv:
    JUDGE_PROVIDER = "gemini"
elif "--ollama" in sys.argv:
    JUDGE_PROVIDER = "ollama"

# Penamaan model mengikuti konvensi LiteLLM: "gemini/<nama-model>" untuk
# Google AI Studio.
#
# JANGAN memakai alias "gemini-flash-latest" di sini. Alias itu menunjuk ke
# model flagship terbaru, dan justru model terbarulah yang jatah gratisnya
# paling sempit — terukur: gemini-3.6-flash hanya 20 permintaan PER HARI
# (quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier). Satu evaluasi
# 3 pertanyaan saja sudah menembusnya, lalu sisa metriknya pulang sebagai nan.
#
# Varian "-lite" yang setingkat di bawahnya berjatah jauh lebih longgar dan
# lebih dari cukup untuk tugas juri (menilai teks pendek, bukan mengarang).
#
# Jatah dihitung PER MODEL per proyek, jadi kalau satu model kena 429, pindah
# ke model lain memberi jatah baru seketika — tidak perlu menunggu besok.
#
# Untuk laporan yang harus bisa diulang persis, patok versinya lewat env atau
# --judge-model; juri yang diam-diam berganti membuat skor antar-waktu tidak
# sebanding.
GEMINI_MODEL = os.getenv("RAGAS_GEMINI_MODEL", "gemini/gemini-3.1-flash-lite")

# --judge-model=<nama> menang atas env var. Dipakai saat satu model kehabisan
# jatah harian dan evaluasi perlu dilanjutkan memakai model lain.
for _arg in sys.argv[1:]:
    if _arg.startswith("--judge-model"):
        _val = _arg.split("=", 1)[1] if "=" in _arg else sys.argv[sys.argv.index(_arg) + 1]
        GEMINI_MODEL = _val if "/" in _val else f"gemini/{_val}"
        break

# ── Penyetelan RunConfig agar cocok dengan Ollama lokal ───────────
#
# Bawaan RAGAS (timeout=180, max_workers=16) dirancang untuk API cloud yang
# melayani banyak permintaan secara paralel. Ollama TIDAK begitu: satu model
# melayani permintaan satu per satu. Akibatnya bawaan tersebut gagal total:
#
#   1. 16 permintaan ditembakkan sekaligus, tapi Ollama mengantrikannya.
#      Nilai timeout dipasang sebagai request_timeout tiap panggilan HTTP
#      (ragas/llms/base.py), jadi jam permintaan yang masih mengantri sudah
#      berjalan. Permintaan ke-8 dan seterusnya kehabisan waktu sebelum
#      sempat dilayani — seluruh job timeout serentak di detik ke-180.
#   2. Di CPU, SATU generasi saja bisa menembus 180 detik.
#
# Karena Ollama serial, menaikkan max_workers tidak mempercepat apa pun —
# hanya membakar jatah waktu. Maka: pekerja 1, tenggat panjang.
RAGAS_TIMEOUT = int(os.getenv("RAGAS_TIMEOUT", "1800"))
RAGAS_MAX_WORKERS = int(os.getenv("RAGAS_MAX_WORKERS", "1"))

# Bawaan RAGAS mengulang error sampai 10 kali dengan jeda hingga 60 detik —
# masuk akal untuk rate limit API cloud, tapi merugikan di sini: error izin
# atau model tidak ditemukan TIDAK akan sembuh dengan diulang, dan satu job
# bisa membuang ~10 menit hanya untuk gagal. Pengulangan secukupnya saja;
# kegagalan yang tak tersembuhkan sudah dicegat lebih awal oleh preflight.
RAGAS_MAX_RETRIES = int(os.getenv("RAGAS_MAX_RETRIES", "3"))
RAGAS_MAX_WAIT = int(os.getenv("RAGAS_MAX_WAIT", "20"))


class SentenceTransformerEmbeddings(Embeddings):
    """
    Adapter agar model embedding milik aplikasi (bge-m3) bisa dipakai RAGAS.

    Memakai ulang singleton dari embedding_service, bukan memuat salinan kedua —
    model ini berukuran 2,27GB dan pemuatan ganda memboroskan memori dan waktu.
    """

    def __init__(self):
        from app.services.embedding_service import get_embedding_model
        self._model = get_embedding_model()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, show_progress_bar=False).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(text, show_progress_bar=False).tolist()


def build_dataset(rag_rows: list[dict]) -> EvaluationDataset:
    """Ubah hasil pipeline RAG menjadi EvaluationDataset milik RAGAS."""
    samples = []
    for row in rag_rows:
        samples.append(
            SingleTurnSample(
                user_input=row["question"],
                retrieved_contexts=row["contexts"],
                response=row["answer"],
                reference=row["ground_truth"],
            )
        )
    return EvaluationDataset(samples=samples)


def select_questions(dataset: list[dict], argv: list[str]) -> list[dict]:
    """Pilih subset pertanyaan berdasarkan argumen CLI."""
    if "--all" in argv:
        return dataset

    for arg in argv:
        if arg.startswith("--ids"):
            raw = arg.split("=", 1)[1] if "=" in arg else argv[argv.index(arg) + 1]
            wanted = {i.strip() for i in raw.split(",") if i.strip()}
            picked = [d for d in dataset if d["id"] in wanted]
            missing = wanted - {d["id"] for d in picked}
            if missing:
                logger.warning("ID tidak ada di dataset: %s", sorted(missing))
            return picked

        if arg.startswith("--limit"):
            n = int(arg.split("=", 1)[1] if "=" in arg else argv[argv.index(arg) + 1])
            return dataset[:n]

    return dataset[:DEFAULT_LIMIT]


# Metrik yang tersedia. Tiga yang ditandai "berat" menjejalkan SELURUH konteks
# hasil retrieval (rata-rata ~3.600 token pada dokumen ini) ke prompt juri, dan
# itulah penyebab utama lamanya evaluasi di mesin tanpa GPU memadai.
_ALL_METRICS = {
    "faithfulness":       (Faithfulness,                     True),   # berat
    "answer_relevancy":   (ResponseRelevancy,                False),
    "context_recall":     (LLMContextRecall,                 True),   # berat
    "context_precision":  (LLMContextPrecisionWithReference, True),   # berat
    "factual_correctness": (FactualCorrectness,              False),
}

# Preset cepat: hanya metrik yang tidak memproses ulang seluruh konteks.
# Cukup untuk "apakah model saya menjawab dengan benar dan relevan?".
_FAST_PRESET = ["answer_relevancy", "factual_correctness"]


def gemini_temperature(model: str) -> float:
    """
    Suhu untuk model juri Gemini. Bawaan 0.0 demi skor yang bisa diulang.

    Saat dipanggil, Gemini 3+ memunculkan peringatan bahwa suhu < 1.0 dapat
    menyebabkan "infinite loops, degraded reasoning performance, and failure on
    complex tasks", dan menganjurkan 1.0. Anjuran itu SENGAJA tidak diikuti di
    sini, karena diuji langsung pada gemini-3.1-flash-lite dan hasilnya justru
    kebalikannya untuk tugas menilai:

      Kasus jelas (semua klaim ada di konteks, skor benar = 1.0)
        suhu 0.0 -> 1.00, 1.00, 1.00      suhu 1.0 -> 1.00, 1.00, 1.00
      Kasus abu-abu (jawaban hanya memuat sebagian isi yang ditanyakan)
        suhu 0.0 -> 0.00, 0.00            suhu 1.0 -> 1.00, 0.00   <-- goyang

    Pada input yang IDENTIK, suhu 1.0 memberi dua skor berbeda. Untuk laporan
    evaluasi itu fatal: angka yang berubah tiap kali dijalankan tidak bisa
    dipertanggungjawabkan, dan perbandingan antar model jadi tak bermakna.
    Tidak ada gejala infinite loop maupun penalaran menurun yang teramati.

    Bila suatu saat benar-benar menemui jawaban juri yang mandek atau ngawur,
    naikkan lewat env tanpa mengubah kode:
        RAGAS_JUDGE_TEMPERATURE=1.0
    """
    return float(os.getenv("RAGAS_JUDGE_TEMPERATURE", "0.0"))


def _preflight_gemini(api_key: str) -> None:
    """
    Pastikan Gemini benar-benar bisa dipakai sebelum evaluasi dimulai.

    Memanggil satu prompt sepele (tidak ada isi dokumen yang dikirim). Bila
    gagal, hentikan sekarang dengan pesan yang menjelaskan — jauh lebih baik
    daripada membiarkan RAGAS mengulang error berjam-jam.
    """
    import litellm

    litellm.suppress_debug_info = True
    try:
        litellm.completion(
            model=GEMINI_MODEL,
            messages=[{"role": "user", "content": "Balas satu kata: OK"}],
            max_tokens=10,
            temperature=gemini_temperature(GEMINI_MODEL),
        )
    except Exception as e:
        detail = str(e).replace(api_key, "<KEY-DISENSOR>") if api_key else str(e)

        hint = ""
        if "PERMISSION_DENIED" in detail or "403" in detail:
            fmt = "berformat AIza" if api_key.startswith("AIza") else (
                f"BUKAN berformat AIza (diawali '{api_key[:4]}...')"
            )
            hint = (
                "\nProyek Google-mu menolak permintaan generate.\n"
                f"Key yang dipakai {fmt} — key Google AI Studio diawali 'AIza'.\n"
                "Buat key baru di https://aistudio.google.com/apikey (lewat AI Studio,\n"
                "bukan Cloud Console), setujui Terms of Service bila diminta.\n"
            )
        elif "RESOURCE_EXHAUSTED" in detail or "429" in detail:
            hint = (
                f"\nJatah gratis harian model '{GEMINI_MODEL}' sudah habis.\n"
                "Jatah dihitung PER MODEL, jadi pindah model memberi jatah baru\n"
                "seketika — tidak perlu menunggu besok:\n\n"
                "    python test_ragas_official.py --gemini --judge-model=gemini-3.5-flash-lite --limit 3\n\n"
                "Kalau semua model sudah terpakai, kurangi jumlah panggilan:\n"
                "    tambahkan --fast (melewati context_precision yang paling boros)\n"
            )
        elif "NOT_FOUND" in detail or "404" in detail:
            hint = (
                f"\nModel '{GEMINI_MODEL}' tidak tersedia untuk akunmu.\n"
                "Lihat daftar model yang boleh dipakai key ini:\n"
                "    python test_ragas_official.py --list-models\n"
                "lalu pilih salah satu lewat --judge-model=<nama>\n"
            )

        raise SystemExit(
            f"Uji koneksi Gemini GAGAL — evaluasi dihentikan sebelum dimulai.\n{hint}"
            f"\nPesan asli:\n  {detail[:400]}\n"
            "\nAlternatif: hapus RAGAS_JUDGE_PROVIDER untuk memakai juri lokal (Ollama)."
        )

    print(f"         Uji koneksi Gemini: OK ({GEMINI_MODEL})")


def build_judge():
    """
    Bentuk model juri sesuai RAGAS_JUDGE_PROVIDER.

    Returns:
        Objek LLM yang bisa dipakai ragas.evaluate(llm=...).
    """
    if JUDGE_PROVIDER == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise SystemExit(
                "RAGAS_JUDGE_PROVIDER=gemini tetapi API key tidak ditemukan.\n"
                "Ambil key gratis di https://aistudio.google.com/apikey, lalu tambahkan\n"
                "ke file .env:\n\n"
                "    GEMINI_API_KEY=isi-key-anda-di-sini\n"
            )

        # Uji satu panggilan kecil DULU. Tanpa ini, kegagalan izin (403) baru
        # ketahuan setelah evaluasi berjalan lama: RAGAS memperlakukan error
        # sebagai gangguan sementara dan mengulanginya sampai 10 kali dengan
        # jeda hingga 60 detik, sehingga tiap job membuang ~10 menit hanya
        # untuk gagal. Error izin tidak akan pernah sembuh dengan diulang.
        _preflight_gemini(api_key)

        import instructor
        import litellm
        from ragas.llms import llm_factory

        litellm.suppress_debug_info = True

        # Adapter litellm milik ragas memanggil client lewat
        # `client.chat.completions.create(...)` (ragas/llms/litellm_llm.py),
        # jadi modul litellm TIDAK bisa dipakai langsung sebagai client —
        # modulnya tidak punya atribut `.chat`.
        #
        # instructor.from_litellm() membungkusnya jadi AsyncInstructor yang
        # menyediakan antarmuka itu. Versi async dipilih karena metrik ragas
        # dijalankan asinkron, dan adapter memeriksa AsyncInstructor lebih dulu.
        client = instructor.from_litellm(litellm.acompletion)

        temp = gemini_temperature(GEMINI_MODEL)
        if temp > 0:
            print(f"         Suhu juri: {temp} — skor TIDAK bisa diulang persis "
                  "(bawaan 0.0 dipilih agar hasil konsisten)")

        return llm_factory(
            GEMINI_MODEL,
            provider="google",
            client=client,
            adapter="litellm",
            temperature=temp,
        )

    if JUDGE_PROVIDER != "ollama":
        raise SystemExit(
            f"RAGAS_JUDGE_PROVIDER tidak dikenal: '{JUDGE_PROVIDER}' "
            "(pilihan: ollama, gemini)"
        )

    return LangchainLLMWrapper(
        ChatOllama(
            model=JUDGE_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            # Matikan mode thinking: pada model seperti qwen3.5 yang aktif secara
            # default, seluruh anggaran token habis untuk penalaran internal dan
            # jawabannya pulang kosong sehingga semua metrik jadi 0.
            reasoning=False,
        )
    )


def judge_label() -> str:
    """Nama juri untuk ditampilkan dan dicatat di laporan."""
    return GEMINI_MODEL if JUDGE_PROVIDER == "gemini" else JUDGE_MODEL


def select_metrics(argv: list[str]):
    """Pilih metrik dari argumen CLI. Tanpa argumen: seluruh lima metrik."""
    chosen = None

    if "--fast" in argv:
        chosen = _FAST_PRESET
    else:
        for arg in argv:
            if arg.startswith("--metrics"):
                raw = arg.split("=", 1)[1] if "=" in arg else argv[argv.index(arg) + 1]
                chosen = [m.strip() for m in raw.split(",") if m.strip()]
                break

    if chosen is None:
        chosen = list(_ALL_METRICS)

    unknown = [m for m in chosen if m not in _ALL_METRICS]
    if unknown:
        raise SystemExit(
            f"Metrik tidak dikenal: {unknown}\nPilihan: {', '.join(_ALL_METRICS)}"
        )
    return [_ALL_METRICS[m][0]() for m in chosen]


# Perkiraan jumlah panggilan juri per PERTANYAAN untuk tiap metrik, dibaca dari
# kode ragas 0.4.3:
#   faithfulness        statement_generator + nli                        = 2
#   answer_relevancy    generate_multiple(n=strictness=3)                = 3
#   context_recall      satu panggilan untuk seluruh konteks             = 1
#   factual_correctness dekomposisi klaim ×2 + nli ×2 (mode f1)          = 4
#   context_precision   SATU PANGGILAN PER POTONGAN KONTEKS  ← lihat bawah
#
# context_precision sengaja tidak ditulis sebagai angka tetap: metrik ini
# melooping `for context in retrieved_contexts` (ragas/metrics/_context_precision.py),
# jadi ongkosnya = jumlah chunk yang diambil retrieval. Pada pertanyaan
# bertipe daftar, retrieval memasok sampai 20 chunk — satu pertanyaan saja
# bisa memakan 20 permintaan. Inilah alasan jatah gratis cepat habis.
_CALLS_PER_QUESTION = {
    "faithfulness": 2,
    "answer_relevancy": 3,
    "context_recall": 1,
    "factual_correctness": 4,
}
_PER_CONTEXT_METRICS = {"llm_context_precision_with_reference", "context_precision"}


def estimate_judge_calls(metrics, rag_rows: list[dict]) -> tuple[int, list[str]]:
    """
    Taksir berapa permintaan yang akan dikirim ke juri, dan rinciannya.

    Berguna khusus untuk juri berkuota harian: lebih baik tahu bahwa anggaran
    akan jebol SEBELUM evaluasi dimulai daripada menemukan separuh metrik
    bernilai nan setelah menunggu lama.
    """
    total = 0
    lines = []
    n_q = len(rag_rows)

    for metric in metrics:
        # Sebagian metrik menyisipkan parameter ke namanya, mis.
        # "factual_correctness(mode=f1)". Buang bagian itu agar cocok di tabel.
        name = metric.name.split("(", 1)[0]
        if name in _PER_CONTEXT_METRICS:
            calls = sum(len(row["contexts"]) for row in rag_rows)
            note = f"{calls:4d}  ({calls // max(n_q, 1)} chunk/pertanyaan — 1 panggilan per chunk)"
        else:
            per_q = _CALLS_PER_QUESTION.get(name, 1)
            calls = per_q * n_q
            note = f"{calls:4d}  ({per_q} × {n_q} pertanyaan)"
        total += calls
        lines.append(f"           {name:36s} {note}")

    return total, lines


# Cache hasil FASE 1 (jawaban + konteks dari pipeline RAG lokal).
#
# Fase 1 berjalan di Ollama dan memakan waktu menit per pertanyaan, sedangkan
# fase 2 (penilaian) bisa gagal di tengah jalan karena jatah juri habis. Tanpa
# cache, setiap percobaan ulang penilaian memaksa seluruh generasi lokal
# diulang dari nol padahal hasilnya akan persis sama.
#
# Cache hanya sah bila pertanyaan DAN model generasi sama — mengganti salah
# satunya berarti yang dievaluasi sudah beda, jadi cache diabaikan.
_PHASE1_CACHE = ".ragas_cache_phase1.json"


def load_phase1_cache(ids: list[str], gen_model: str) -> list[dict] | None:
    """Kembalikan hasil fase 1 dari cache bila cocok, selain itu None."""
    if not os.path.exists(_PHASE1_CACHE):
        return None
    try:
        with open(_PHASE1_CACHE, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if cached.get("gen_model") != gen_model:
        print(f"         Cache diabaikan: dibuat dengan model '{cached.get('gen_model')}'")
        return None
    if [r["id"] for r in cached.get("rows", [])] != ids:
        print("         Cache diabaikan: daftar pertanyaan berbeda")
        return None

    return cached["rows"]


def save_phase1_cache(rows: list[dict], gen_model: str) -> None:
    """Simpan hasil fase 1 agar penilaian bisa diulang tanpa generasi ulang."""
    try:
        with open(_PHASE1_CACHE, "w", encoding="utf-8") as f:
            json.dump({"gen_model": gen_model, "rows": rows}, f, ensure_ascii=False)
    except OSError as e:
        logger.warning("Gagal menyimpan cache fase 1: %s", e)


def list_gemini_models() -> None:
    """Cetak model yang boleh dipakai API key ini, lalu keluar."""
    import json as _json
    import urllib.request

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY belum diisi di .env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        f"?key={api_key}&pageSize=200"
    )
    data = _json.load(urllib.request.urlopen(url))
    print("\nModel yang mendukung generateContent untuk key ini:\n")
    for m in data.get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print(f"  {m['name'].replace('models/', '')}")
    print(
        "\nPakai salah satunya:  --judge-model=<nama>\n"
        "Varian '-lite' berjatah gratis paling longgar; model flagship terbaru\n"
        "justru paling sempit (gemini-3.6-flash hanya 20 permintaan/hari).\n"
    )
    raise SystemExit(0)


def save_report(result, rows: list[dict], gen_model: str) -> None:
    """Tulis laporan markdown dari hasil evaluate()."""
    df = result.to_pandas()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("# Laporan Evaluasi RAG — RAGAS (library resmi)\n\n")
        f.write(f"> Model generasi: `{gen_model}` · Model juri: `{judge_label()}` ({JUDGE_PROVIDER})\n")
        f.write(f"> Embedding: `{settings.EMBEDDING_MODEL_NAME}`\n")
        f.write(f"> Ground truth: `reference_eval_dataset.json` ({len(rows)} pertanyaan)\n\n")

        f.write("## Ringkasan Skor\n\n| Metrik | Skor |\n|--------|------|\n")
        for name, value in result._repr_dict.items():
            f.write(f"| **{name}** | `{value:.4f}` |\n")

        f.write("\n---\n\n## Detail per Pertanyaan\n\n")
        metric_cols = [c for c in df.columns
                       if c not in ("user_input", "retrieved_contexts", "response", "reference")]
        for i, row in df.iterrows():
            meta = rows[i]
            f.write(f"### {meta['id']} — {meta.get('category', '-')}\n\n")
            f.write(f"**Q:** {row['user_input']}\n\n")
            f.write(f"**Jawaban RAG:** {row['response']}\n\n")
            f.write(f"**Ground truth:** {row['reference']}\n\n")
            if meta.get("notes"):
                f.write(f"> **Catatan:** {meta['notes']}\n\n")
            f.write("| Metrik | Skor |\n|--------|------|\n")
            for c in metric_cols:
                val = row[c]
                shown = f"{val:.4f}" if isinstance(val, (int, float)) else str(val)
                f.write(f"| {c} | `{shown}` |\n")
            f.write("\n---\n\n")

    # print, bukan logger: logger menulis ke stderr sedangkan kemajuan fase
    # dicetak ke stdout, sehingga baris ini muncul MENDAHULUI "[FASE 3]" yang
    # seharusnya lebih dulu. Satu saluran saja supaya urutannya benar.
    print(f"         Laporan disimpan ke: {OUTPUT_PATH}")


if __name__ == "__main__":
    if "--list-models" in sys.argv:
        list_gemini_models()

    gen_model = settings.LLM_MODEL_NAME

    print("\n" + "=" * 62)
    print("  EVALUASI RAG — RAGAS (library resmi)")
    print(f"  Model generasi : {gen_model}")
    print(f"  Model juri     : {judge_label()}  [{JUDGE_PROVIDER}]")
    print(f"  Embedding      : {settings.EMBEDDING_MODEL_NAME}")
    print("=" * 62)

    if JUDGE_PROVIDER == "gemini":
        print("\n  [CATATAN] Juri berjalan di server Google — pertanyaan, jawaban,")
        print("  dan seluruh isi konteks dokumen dikirim keluar dari mesin ini.\n")

    if JUDGE_PROVIDER == "ollama" and JUDGE_MODEL == gen_model:
        print("\n  [PERINGATAN] Model juri sama dengan model generasi — model menilai")
        print("  jawabannya sendiri. Untuk membandingkan antar model, set")
        print("  RAGAS_EVAL_MODEL ke satu model tetap.\n")

    dataset = load_reference_dataset()
    selected = select_questions(dataset, sys.argv[1:])
    ids = [d["id"] for d in selected]

    print(f"\n[FASE 1] Menjalankan {len(selected)} pertanyaan lewat pipeline RAG...")
    print(f"         ID: {', '.join(ids)}")

    rag_rows = None
    if "--reuse" in sys.argv:
        rag_rows = load_phase1_cache(ids, gen_model)
        if rag_rows:
            print(f"         DILEWATI — memakai cache {_PHASE1_CACHE} "
                  f"({len(rag_rows)} pertanyaan, model '{gen_model}')")

    if rag_rows is None:
        rag_rows = collect_rag_data(selected)
        save_phase1_cache(rag_rows, gen_model)
        print(f"         Hasil disimpan ke {_PHASE1_CACHE} — "
              "ulangi dengan --reuse untuk melewati fase ini")

    print("\n[FASE 2] Menilai dengan metrik RAGAS...")
    judge = build_judge()
    embeddings = LangchainEmbeddingsWrapper(SentenceTransformerEmbeddings())

    metrics = select_metrics(sys.argv[1:])
    print(f"         Metrik: {', '.join(m.name for m in metrics)}")

    run_config = RunConfig(
        timeout=RAGAS_TIMEOUT,
        max_workers=RAGAS_MAX_WORKERS,
        max_retries=RAGAS_MAX_RETRIES,
        max_wait=RAGAS_MAX_WAIT,
    )
    print(f"         RunConfig: timeout={RAGAS_TIMEOUT}s, max_workers={RAGAS_MAX_WORKERS}, "
          f"max_retries={RAGAS_MAX_RETRIES}, max_wait={RAGAS_MAX_WAIT}s")
    print("         (bawaan RAGAS 180s/16 pekerja/10 ulangan tidak cocok di sini)")

    # Juri Gemini gratis dibatasi per HARI. Tampilkan anggaran permintaannya
    # lebih dulu supaya kehabisan jatah ketahuan sebelum menunggu, bukan
    # sesudah — 429 di tengah jalan membuat metrik sisanya bernilai nan.
    est_calls, est_lines = estimate_judge_calls(metrics, rag_rows)
    print(f"\n         Perkiraan permintaan ke juri: ~{est_calls}")
    for line in est_lines:
        print(line)
    if JUDGE_PROVIDER == "gemini" and est_calls > 20:
        print("\n         [PERINGATAN] Beberapa model gratis berjatah hanya 20 permintaan/hari.")
        print("         Bila kena 429: ulangi dengan --fast, atau pindah model dengan")
        print("         --judge-model=<nama> (jatah dihitung per model, lihat --list-models).")

    result = evaluate(
        dataset=build_dataset(rag_rows),
        metrics=metrics,
        llm=judge,
        embeddings=embeddings,
        run_config=run_config,
    )

    # Seluruh pekerjaan asinkron sudah selesai di sini. Koneksi HTTPS ke Gemini
    # yang masih terbuka baru dibereskan saat interpreter ditutup — dan saat itu
    # event loop sudah tertutup lebih dulu, sehingga asyncio membuang
    # "Fatal error on SSL transport" + "RuntimeError: Event loop is closed"
    # sebanyak koneksi yang tersisa.
    #
    # Semua itu terjadi SETELAH skor dihitung dan laporan ditulis: tidak ada
    # hasil yang terpengaruh. Tapi dinding traceback di akhir layar membuat run
    # yang sukses terlihat gagal total, jadi kebisingan itu dibungkam.
    #
    # Dibungkam DI SINI, bukan di awal file: selama evaluasi berlangsung, error
    # asyncio yang sesungguhnya tetap harus terlihat.
    #
    # Perlu DUA tambalan karena kebisingannya datang lewat dua jalur berbeda:
    #   1. logger "asyncio"  -> "Fatal error on SSL transport"
    #   2. unraisablehook    -> "Exception ignored in: _SSLProtocolTransport.__del__",
    #      dicetak interpreter saat objek soket dibuang garbage collector,
    #      sama sekali tidak lewat logging sehingga tak bisa dibungkam logger.
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    def _abaikan_kebisingan_penutupan(unraisable):
        """Telan HANYA error penutupan event loop; sisanya diteruskan apa adanya."""
        exc = unraisable.exc_value
        if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
            return
        sys.__unraisablehook__(unraisable)

    sys.unraisablehook = _abaikan_kebisingan_penutupan

    print("\n[FASE 3] Menyimpan laporan...")
    save_report(result, rag_rows, gen_model)

    print("\n" + "=" * 62)
    print("  HASIL AKHIR")
    failed = []
    for name, value in result._repr_dict.items():
        print(f"  {name:36s} : {value:.4f}")
        if value != value:  # nan != nan
            failed.append(name)
    print("=" * 62)

    # nan bukan skor buruk — artinya metrik itu tidak pernah selesai dihitung.
    # Bedakan dengan tegas, supaya laporan tidak dibaca sebagai "sistem gagal"
    # padahal yang gagal adalah panggilan ke juri.
    if failed:
        print(f"\n  [PERHATIAN] {len(failed)} metrik bernilai nan: {', '.join(failed)}")
        print("  nan BUKAN nilai nol — metriknya gagal dihitung, bukan dinilai jelek.")
        print("  Penyebab tersering pada juri Gemini gratis: jatah harian habis (429).")
        print("  Gulir ke atas dan cari 'RESOURCE_EXHAUSTED' untuk memastikan.")
        print("\n  Cara melanjutkan:")
        print("    python test_ragas_official.py --gemini --limit 3 --judge-model=gemini-3.5-flash-lite")
        print("    python test_ragas_official.py --gemini --limit 3 --fast   # paling hemat")
