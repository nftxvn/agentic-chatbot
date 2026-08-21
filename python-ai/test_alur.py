"""
Menelusuri alur dokumen dari PDF sampai siap di-embed, satu tahap satu bagian.

Bacalah dari atas ke bawah — urutan kelasnya SAMA dengan urutan yang dilalui
dokumen sungguhan:

    TAHAP 1  Ekstraksi     PDF        -> teks per halaman
    TAHAP 2  Konteks       halaman    -> label isi halaman
    TAHAP 3  Pemotongan    halaman    -> potongan induk + anak
    TAHAP 4  Siap embed    potongan   -> bentuk yang diterima ChromaDB

Berjalan TANPA Ollama dan TANPA OCR: tahap 1 memakai hasil ekstraksi yang
sudah tersimpan di data/ekstraksi_1.json. Itu disengaja — OCR memakan ~25 menit
dan hasilnya tidak deterministik, sehingga tidak layak jadi bahan uji otomatis.
Yang diuji di sini adalah tahap-tahap SESUDAHnya, yang seluruhnya deterministik.

Jalankan:
    python test_alur.py                  # dengan penjelasan tiap tahap
    python -m unittest test_alur -q      # ringkas, hanya lolos/gagal
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services import embedding_service as es  # noqa: E402

BERKAS_EKSTRAKSI = Path("data/ekstraksi_1.json")

# Dicetak hanya saat dijalankan langsung, supaya `python -m unittest` tetap ringkas.
CERITA = __name__ == "__main__"


def kabar(*isi: object) -> None:
    if CERITA:
        print(*isi)


class Alur:
    """
    Wadah bersama antar tahap.

    Sengaja dihitung SEKALI lalu dipakai ulang: memuat model dan memotong ulang
    di tiap test membuat berkas ini lambat, dan yang diuji memang satu aliran
    yang sama — bukan empat aliran terpisah.
    """

    halaman: list[dict] = []
    judul: str | None = None
    induk: list[dict] = []
    anak: list[dict] = []


def setUpModule() -> None:
    if not BERKAS_EKSTRAKSI.exists():
        raise unittest.SkipTest(
            f"{BERKAS_EKSTRAKSI} belum ada. Jalankan dulu:\n"
            '    python ingest_dokumen.py --file "test_files/SOP-diskominfotik 2025-1-10.pdf" --id 1 --pratinjau'
        )

    Alur.halaman = json.loads(BERKAS_EKSTRAKSI.read_text(encoding="utf-8"))
    Alur.judul = es.derive_document_title(Alur.halaman)
    Alur.induk, Alur.anak = es.chunk_text_hierarchical(
        Alur.halaman, document_title=Alur.judul
    )


# ══════════════════════════════════════════════════════════════════
# TAHAP 1 — Ekstraksi:  PDF  ->  teks per halaman
# ══════════════════════════════════════════════════════════════════
class Tahap1Ekstraksi(unittest.TestCase):
    """
    Keluaran tahap ini adalah daftar halaman: [{page_number, text}, ...].

    Semua tahap sesudahnya berdiri di atasnya, jadi bentuknya diperiksa dulu
    sebelum isinya. Halaman yang kosong tidak menimbulkan galat di mana pun —
    ia hanya menghilang diam-diam dari korpus.
    """

    def test_setiap_halaman_punya_nomor_dan_teks(self):
        kabar(f"\n  TAHAP 1 — {len(Alur.halaman)} halaman terekstrak")
        for h in Alur.halaman:
            with self.subTest(halaman=h.get("page_number")):
                self.assertIn("page_number", h)
                self.assertIn("text", h)
                self.assertTrue(h["text"].strip(), "halaman kosong")

    def test_nomor_halaman_berurutan_tanpa_bolong(self):
        nomor = sorted(h["page_number"] for h in Alur.halaman)
        self.assertEqual(nomor, list(range(1, len(nomor) + 1)))

    def test_judul_dokumen_bisa_diturunkan(self):
        """Judul jadi '[Topik Utama: ...]' pada SETIAP potongan, jadi ia penting."""
        kabar(f"           judul: {(Alur.judul or '(tidak terdeteksi)')[:66]}")
        self.assertTrue(Alur.judul)


# ══════════════════════════════════════════════════════════════════
# TAHAP 2 — Konteks:  halaman  ->  label isi halaman
# ══════════════════════════════════════════════════════════════════
class Tahap2Konteks(unittest.TestCase):
    """
    Tiap halaman diberi satu label yang diturunkan dari isinya sendiri —
    bukan dari kamus yang dipatok, supaya berlaku untuk dokumen apa pun.

    Halaman tanpa penanda MEWARISI label halaman sebelumnya. Pada korpus ini
    daftar 74 SOP terbentang di empat halaman dan tiga di antaranya tidak
    memuat satu baris judul pun; tanpa warisan, ketiganya masuk korpus tanpa
    konteks — padahal justru itu halaman yang paling membutuhkannya.
    """

    def konteks(self, nomor_halaman: int) -> str | None:
        for c in Alur.induk:
            if c["page_number"] == nomor_halaman:
                for baris in c["text"].split("\n"):
                    if baris.startswith("[Konteks:"):
                        return baris[len("[Konteks:"):].rstrip("]").strip()
        return None

    def test_tidak_ada_halaman_tanpa_konteks(self):
        kabar("\n  TAHAP 2 — konteks per halaman")
        for h in Alur.halaman:
            nomor = h["page_number"]
            with self.subTest(halaman=nomor):
                label = self.konteks(nomor)
                kabar(f"           hal {nomor:>2}: {label}")
                self.assertIsNotNone(label, f"halaman {nomor} tanpa konteks")

    def test_halaman_lanjutan_mewarisi_label_halaman_kepala(self):
        """
        Formulir SOP terdiri dari dua halaman; hanya halaman pertama yang
        memuat baris 'Nama SOP'. Halaman keduanya harus ikut label yang sama,
        kalau tidak ia tidak akan pernah ditemukan lewat nama prosedurnya.
        """
        teks_per_halaman = {h["page_number"]: h["text"] for h in Alur.halaman}

        # Halaman lanjutan = berlabel SOP, tetapi baris 'Nama SOP' tidak ada di
        # teksnya sendiri. Label itu hanya bisa datang dari warisan.
        lanjutan = [
            nomor for nomor, teks in teks_per_halaman.items()
            if (self.konteks(nomor) or "").startswith("SOP ")
            and "nama sop" not in teks.lower()
        ]
        if not lanjutan:
            self.skipTest("korpus ini tidak memuat halaman lanjutan formulir SOP")

        for nomor in lanjutan:
            with self.subTest(halaman=nomor):
                self.assertEqual(
                    self.konteks(nomor - 1), self.konteks(nomor),
                    f"halaman {nomor} lanjutan dari {nomor - 1} tapi labelnya beda",
                )

    def test_label_tidak_diambil_dari_blok_tanda_tangan(self):
        """
        Kaki halaman memuat nama pejabat dalam huruf besar. Kalau ia sempat
        dihitung sebagai judul bagian, halaman daftar terlabeli nama pejabat
        alih-alih bagian yang memuat daftarnya.
        """
        for h in Alur.halaman:
            label = self.konteks(h["page_number"]) or ""
            with self.subTest(halaman=h["page_number"]):
                self.assertNotIn("WALI KOTA", label.upper())
                self.assertNotIn("NIP", label.upper())


# ══════════════════════════════════════════════════════════════════
# TAHAP 3 — Pemotongan:  halaman  ->  potongan induk + anak
# ══════════════════════════════════════════════════════════════════
class Tahap3Pemotongan(unittest.TestCase):
    """
    Dua lapis, dua kegunaan berbeda:

      induk  — potongan besar, DIKIRIM KE LLM sebagai konteks jawaban
      anak   — potongan kecil, DI-EMBED sebagai indeks pencarian

    Tiap anak menunjuk induknya lewat `parent_index`. Pencarian menemukan anak,
    lalu yang dikirim ke LLM adalah induknya — sehingga model menerima potongan
    utuh, bukan penggalan 300 karakter.
    """

    def test_setiap_halaman_menghasilkan_potongan(self):
        kabar(f"\n  TAHAP 3 — {len(Alur.induk)} induk, {len(Alur.anak)} anak")
        halaman_berinduk = {c["page_number"] for c in Alur.induk}
        for h in Alur.halaman:
            with self.subTest(halaman=h["page_number"]):
                self.assertIn(h["page_number"], halaman_berinduk)

    def test_setiap_anak_menunjuk_induk_yang_ada(self):
        """
        Anak yatim tersimpan TANPA galat apa pun, lalu LLM menerima konteks
        milik potongan lain. Kegagalan diam seperti ini yang paling mahal.
        """
        induk_per_halaman = {}
        for c in Alur.induk:
            induk_per_halaman.setdefault(c["page_number"], set()).add(c["chunk_index"])

        for a in Alur.anak:
            with self.subTest(anak=a["chunk_index"]):
                self.assertIn(
                    a["parent_index"],
                    induk_per_halaman.get(a["page_number"], set()),
                    f"anak {a['chunk_index']} menunjuk induk yang tidak ada",
                )

    def test_anak_lebih_kecil_daripada_induknya(self):
        induk_teks = {(c["page_number"], c["chunk_index"]): c["text"] for c in Alur.induk}
        for a in Alur.anak:
            kunci = (a["page_number"], a["parent_index"])
            with self.subTest(anak=a["chunk_index"]):
                self.assertLessEqual(len(a["text"]), len(induk_teks[kunci]))

    def test_setiap_potongan_membawa_halaman_dan_topiknya(self):
        """Prefiks inilah yang membuat potongan tetap bermakna saat berdiri sendiri."""
        for c in Alur.induk + Alur.anak:
            with self.subTest(halaman=c["page_number"]):
                self.assertIn(f"[Halaman {c['page_number']}]", c["text"])
                self.assertIn("[Topik Utama:", c["text"])


# ══════════════════════════════════════════════════════════════════
# TAHAP 4 — Siap embed:  potongan  ->  bentuk yang diterima ChromaDB
# ══════════════════════════════════════════════════════════════════
class Tahap4SiapEmbedding(unittest.TestCase):
    """
    Tahap terakhir sebelum vektor masuk korpus. Yang diperiksa di sini bukan
    kualitas isinya lagi, melainkan apakah bentuknya tidak akan ditolak atau —
    lebih buruk — diterima diam-diam dalam keadaan cacat.
    """

    def test_tidak_ada_potongan_kosong(self):
        for c in Alur.induk + Alur.anak:
            with self.subTest(halaman=c["page_number"]):
                self.assertTrue(c["text"].strip())

    def test_metadata_lengkap(self):
        for c in Alur.induk:
            self.assertIsInstance(c["page_number"], int)
            self.assertIsInstance(c["chunk_index"], int)
        for a in Alur.anak:
            self.assertIsInstance(a["parent_index"], int)

    def test_tidak_ada_anak_kembar(self):
        """Anak identik memakan slot hasil pencarian tanpa menambah informasi."""
        teks = [a["text"] for a in Alur.anak]
        kembar = len(teks) - len(set(teks))
        self.assertEqual(kembar, 0, f"{kembar} anak berisi teks yang sama persis")

    def test_ringkasan_akhir(self):
        kabar(
            f"\n  TAHAP 4 — siap disimpan: {len(Alur.induk)} induk + "
            f"{len(Alur.anak)} anak = {len(Alur.induk) + len(Alur.anak)} vektor"
        )
        kabar("           masukkan ke korpus:  python ingest_dokumen.py --id 1 --pakai-ekstraksi\n")
        self.assertGreater(len(Alur.induk), 0)


# ══════════════════════════════════════════════════════════════════
# TAHAP 0 — Jeda & lanjut:  ekstraksi panjang yang bisa dihentikan
# ══════════════════════════════════════════════════════════════════
class Tahap0JedaDanLanjut(unittest.TestCase):
    """
    Ekstraksi 171 halaman berjam-jam. Tanpa jeda, satu-satunya cara berhenti
    adalah membunuh worker — dan itu membuang seluruh pekerjaan.

    OCR ditiru dengan fungsi palsu di sini. Yang diuji memang bukan mutu OCR-nya
    melainkan ALURNYA: apa yang tersimpan, kapan berhenti, dan dari mana
    melanjutkan. Memakai OCR sungguhan justru membuat semua itu tidak teruji,
    karena satu putaran perlu 25 menit dan hasilnya tak pernah sama.
    """

    HALAMAN = 6

    def siapkan(self):
        from app.services import ekstraksi_bertahap as eb

        simpanan = eb.PenyimpananMemori()
        dipanggil: list[int] = []

        def ocr(nomor: int, petunjuk: str | None = None) -> tuple[str, str | None]:
            dipanggil.append(nomor)
            # Catatan format menyala di halaman 3 dan terbawa sesudahnya —
            # meniru perilaku formulir SOP yang sebenarnya.
            return f"isi halaman {nomor}", petunjuk or ("format" if nomor >= 3 else None)

        return eb, simpanan, ocr, dipanggil

    def jalankan(self, eb, simpanan, ocr, **kw):
        return eb.ekstrak_bertahap(1, self.HALAMAN, ocr, simpanan, **kw)

    def test_tanpa_jeda_semua_halaman_selesai(self):
        eb, simpanan, ocr, dipanggil = self.siapkan()
        hasil = self.jalankan(eb, simpanan, ocr)
        kabar(f"\n  TAHAP 0 — {hasil.halaman_selesai}/{hasil.halaman_total} halaman, {hasil.status}")
        self.assertEqual(hasil.status, eb.STATUS_SELESAI)
        self.assertEqual(dipanggil, list(range(1, self.HALAMAN + 1)))

    def test_jeda_menyimpan_halaman_yang_sedang_dikerjakan(self):
        """
        Inti rancangannya: halaman yang sedang berjalan DISELESAIKAN dan
        DISIMPAN dulu, baru berhenti. Memeriksa jeda sebelum menyimpan berarti
        membuang halaman yang sudah dibayar dengan puluhan detik OCR.
        """
        eb, simpanan, ocr, dipanggil = self.siapkan()

        def ocr_lalu_minta_jeda(nomor: int, petunjuk: str | None = None):
            hasil = ocr(nomor, petunjuk)
            if nomor == 3:
                simpanan.minta_jeda(1)      # pengguna menekan jeda saat hal. 3 berjalan
            return hasil

        hasil = self.jalankan(eb, simpanan, ocr_lalu_minta_jeda)
        self.assertEqual(hasil.status, eb.STATUS_JEDA)
        self.assertEqual(hasil.halaman_selesai, 3, "halaman ke-3 harus ikut tersimpan")
        self.assertIn(3, simpanan.halaman_tersimpan(1))
        self.assertNotIn(4, dipanggil, "halaman 4 tidak boleh ikut dikerjakan")

    def test_lanjut_meneruskan_dari_halaman_berikutnya(self):
        eb, simpanan, ocr, dipanggil = self.siapkan()
        simpanan.minta_jeda(1)
        for n in (1, 2, 3):
            simpanan.simpan_halaman(1, n, f"isi halaman {n}")

        simpanan.batalkan_jeda(1)
        hasil = self.jalankan(eb, simpanan, ocr)

        kabar(f"           lanjut dari hal 4: {dipanggil}")
        self.assertEqual(hasil.status, eb.STATUS_SELESAI)
        self.assertEqual(dipanggil, [4, 5, 6], "halaman 1-3 tidak boleh di-OCR ulang")

    def test_jeda_sebelum_halaman_pertama_dihormati(self):
        """Pengguna bisa menekan jeda selagi tugas masih mengantre di Celery."""
        eb, simpanan, ocr, dipanggil = self.siapkan()
        simpanan.minta_jeda(1)
        hasil = self.jalankan(eb, simpanan, ocr)
        self.assertEqual(hasil.status, eb.STATUS_JEDA)
        self.assertEqual(dipanggil, [], "tidak satu halaman pun boleh dikerjakan")

    def test_gagal_di_tengah_tidak_menghapus_kemajuan(self):
        """Mati di halaman 4 harus setara dengan jeda di halaman 3."""
        eb, simpanan, ocr, _ = self.siapkan()

        def ocr_gagal(nomor: int, petunjuk: str | None = None):
            if nomor == 4:
                raise TimeoutError("model vision menggantung")
            return ocr(nomor, petunjuk)

        hasil = self.jalankan(eb, simpanan, ocr_gagal)
        self.assertEqual(hasil.status, eb.STATUS_GAGAL)
        self.assertEqual(simpanan.halaman_tersimpan(1), {1, 2, 3})
        self.assertIn("Halaman 4", hasil.pesan or "")

    def test_memanggil_ulang_setelah_selesai_tidak_mengerjakan_apa_apa(self):
        """Tugas Celery bisa dijalankan dua kali; yang kedua harus jadi no-op."""
        eb, simpanan, ocr, dipanggil = self.siapkan()
        self.jalankan(eb, simpanan, ocr)
        dipanggil.clear()

        hasil = self.jalankan(eb, simpanan, ocr)
        self.assertEqual(hasil.status, eb.STATUS_SELESAI)
        self.assertEqual(dipanggil, [])

    def test_batas_halaman_per_putaran(self):
        """Memecah pekerjaan panjang jadi beberapa tugas pendek."""
        eb, simpanan, ocr, dipanggil = self.siapkan()
        hasil = self.jalankan(eb, simpanan, ocr, maks_halaman=2)
        self.assertEqual(hasil.status, eb.STATUS_BERJALAN)
        self.assertEqual(dipanggil, [1, 2])

    def test_halaman_terkumpul_siap_dipotong(self):
        """
        Keluaran akhirnya harus berbentuk sama dengan hasil ekstraksi biasa,
        supaya tahap 2-4 di berkas ini tidak perlu tahu asal-usulnya.
        """
        eb, simpanan, ocr, _ = self.siapkan()
        self.jalankan(eb, simpanan, ocr)
        halaman = simpanan.teks_terkumpul(1)

        self.assertEqual(len(halaman), self.HALAMAN)
        self.assertEqual([h["page_number"] for h in halaman], list(range(1, self.HALAMAN + 1)))
        for h in halaman:
            self.assertTrue(h["text"].strip())


# ══════════════════════════════════════════════════════════════════
# TAHAP 3b — Citra halaman:  PDF  ->  JPEG untuk editor koreksi
# ══════════════════════════════════════════════════════════════════
class Tahap3CitraHalaman(unittest.TestCase):
    """
    Korektor tidak bisa memperbaiki apa yang tidak bisa ia lihat.

    Kegagalan OCR yang paling sering pada dokumen pindaian bukan salah ketik
    melainkan BARIS YANG HILANG — nama SOP, blok NIP, penanda daftar. Yang
    hilang tidak meninggalkan jejak di teks, jadi satu-satunya cara
    menemukannya adalah membandingkan dengan citra halaman aslinya.
    """

    PDF = Path("test_files/SOP-diskominfotik 2025-1-10.pdf")

    @classmethod
    def setUpClass(cls):
        if not cls.PDF.exists():
            raise unittest.SkipTest(f"{cls.PDF} tidak ada")

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.routers import documents

        # Basis data ditukar dengan fungsi palsu: yang diuji adalah lapisan
        # HTTP dan perenderannya, bukan SQLAlchemy.
        cls.asli = documents.get_document_by_id
        documents.get_document_by_id = lambda doc_id: (
            {"id": 1, "file_path": str(cls.PDF)} if doc_id == 1
            else {"id": 2, "file_path": "berkas/tidak/ada.pdf"} if doc_id == 2
            else None
        )

        app = FastAPI()
        app.include_router(documents.router)
        app.dependency_overrides[documents.verify_token] = lambda: "uji"
        cls.klien = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.routers import documents
        documents.get_document_by_id = cls.asli

    def test_mengembalikan_jpeg(self):
        r = self.klien.get("/api/docs/1/halaman/8/citra")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/jpeg")
        self.assertEqual(r.content[:3], b"\xff\xd8\xff", "bukan berkas JPEG")
        kabar(f"\n  TAHAP 3b — hal 8 zoom bawaan: {len(r.content)/1024:.0f} KB, "
              f"{r.headers['X-Lebar-Piksel']}x{r.headers['X-Tinggi-Piksel']}")

    def test_zoom_bawaan_sama_dengan_yang_dibaca_model(self):
        """
        Syarat, bukan kebetulan. Kalau korektor melihat gambar lebih tajam
        daripada yang dibaca model, ia memperbaiki teks yang mustahil terbaca
        model dan mengira masalahnya selesai — padahal itu pertanda resolusi
        render yang kurang.
        """
        from app.services import pdf_processor

        bawaan = self.klien.get("/api/docs/1/halaman/8/citra")
        eksplisit = self.klien.get(
            f"/api/docs/1/halaman/8/citra?zoom={pdf_processor.ZOOM_OCR}"
        )
        self.assertEqual(bawaan.headers["X-Lebar-Piksel"],
                         eksplisit.headers["X-Lebar-Piksel"])

    def test_zoom_lebih_besar_menghasilkan_gambar_lebih_besar(self):
        kecil = self.klien.get("/api/docs/1/halaman/8/citra?zoom=1.5")
        besar = self.klien.get("/api/docs/1/halaman/8/citra?zoom=4")
        self.assertLess(int(kecil.headers["X-Lebar-Piksel"]),
                        int(besar.headers["X-Lebar-Piksel"]))
        self.assertLess(len(kecil.content), len(besar.content))

    def test_zoom_sembarang_ditolak(self):
        """Tanpa daftar tertutup, zoom=50 merender gambar 46.000 piksel."""
        for z in (50, 0, -2, 2.5):
            with self.subTest(zoom=z):
                r = self.klien.get(f"/api/docs/1/halaman/8/citra?zoom={z}")
                self.assertEqual(r.status_code, 400)

    def test_halaman_di_luar_jangkauan_404(self):
        r = self.klien.get("/api/docs/1/halaman/999/citra")
        self.assertEqual(r.status_code, 404)

    def test_dokumen_tidak_ada_404(self):
        r = self.klien.get("/api/docs/77/halaman/1/citra")
        self.assertEqual(r.status_code, 404)

    def test_berkas_hilang_404_bukan_500(self):
        """Berkas yang lenyap dari disk adalah 'tidak ada', bukan 'server rusak'."""
        r = self.klien.get("/api/docs/2/halaman/1/citra")
        self.assertEqual(r.status_code, 404)

    def test_boleh_di_cache_selamanya(self):
        r = self.klien.get("/api/docs/1/halaman/8/citra")
        self.assertIn("immutable", r.headers["cache-control"])
        self.assertTrue(r.headers.get("etag"))

    def test_ukuran_halaman_tanpa_merender(self):
        r = self.klien.get("/api/docs/1/halaman/ukuran")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["halaman_total"], 10)
        self.assertEqual(len(data["halaman"]), 10)
        for h in data["halaman"]:
            self.assertIn(h["orientasi"], ("lanskap", "potret"))
            self.assertGreater(h["lebar"], 0)


# ══════════════════════════════════════════════════════════════════
# TAHAP 1b — Petunjuk lengket:  catatan format antar panggilan
# ══════════════════════════════════════════════════════════════════
class Tahap1PetunjukLengket(unittest.TestCase):
    """
    Ekstraksi bertahap memanggil satu halaman per panggilan. Catatan format
    yang ditemukan di halaman kepala harus ikut terbawa ke halaman lanjutan.

    Kalau tidak terbawa, TIDAK ADA GALAT APA PUN: halamannya tetap terekstrak,
    tetap tersimpan, kemajuan tetap bertambah. Yang berubah cuma isinya —
    aturan format tabel prosedur hilang, Waktu dan Output menyatu. Itulah
    sebabnya perilaku ini dikunci uji, bukan diandalkan pada ingatan.

    Model vision diganti fungsi palsu yang MENCATAT petunjuk yang diterimanya.
    Yang diuji memang bukan mutu OCR-nya melainkan apa yang dikirim ke model.
    """

    PDF = Path("test_files/SOP-diskominfotik 2025-1-10.pdf")

    # Halaman kepala: memuat 'Nomor SOP' + 'Nama SOP' sekaligus penanda tabel.
    TEKS_KEPALA = (
        "Nomor SOP: 9/DISKOMINFOTIK/2025\n"
        "Nama SOP: PENYUSUNAN RENCANA STRATEGIS\n"
        "NIP. 196911172001121002\n"
        "No | Uraian Prosedur | Pelaksana | Mutu Baku"
    )
    # Halaman lanjutan: tabel prosedur murni, tanpa kepala sama sekali.
    TEKS_LANJUTAN = (
        "No | Uraian Prosedur | Pelaksana | Mutu Baku\n"
        "1. Menerima surat tentang Penyusunan Renstra"
    )

    def setUp(self):
        if not self.PDF.exists():
            self.skipTest(f"{self.PDF} tidak ada")

        from app.services import pdf_processor as pp

        self.pp = pp
        self.diterima: list[str | None] = []
        self._vision_asli = pp.vision_extract_general
        self._penjaga_asli = pp._ocr_dengan_penjaga
        self.teks_berikut = self.TEKS_KEPALA

        def vision_palsu(img_base64, retries=2, petunjuk=None):
            self.diterima.append(petunjuk)
            return self.teks_berikut

        def penjaga_palsu(img_base64, page_label, petunjuk=None):
            self.diterima.append(petunjuk)
            return self.teks_berikut

        pp.vision_extract_general = vision_palsu
        pp._ocr_dengan_penjaga = penjaga_palsu

    def tearDown(self):
        self.pp.vision_extract_general = self._vision_asli
        self.pp._ocr_dengan_penjaga = self._penjaga_asli

    def test_halaman_kepala_menyalakan_petunjuk_tabel(self):
        _, petunjuk = self.pp.ekstrak_satu_halaman(str(self.PDF), 7, None)
        self.assertIsNotNone(petunjuk, "petunjuk tabel harus menyala di halaman formulir")
        self.assertIn("Mutu Baku", petunjuk)
        kabar(f"\n  TAHAP 1b — halaman 7 menyalakan petunjuk tabel ({len(petunjuk)} huruf)")

    def test_petunjuk_terbawa_ke_panggilan_berikutnya(self):
        """Inti nomor 1: nilai kembalian halaman 7 dipakai halaman 8."""
        _, petunjuk = self.pp.ekstrak_satu_halaman(str(self.PDF), 7, None)

        self.diterima.clear()
        self.teks_berikut = self.TEKS_LANJUTAN
        self.pp.ekstrak_satu_halaman(str(self.PDF), 8, petunjuk)

        self.assertTrue(self.diterima, "model tidak pernah dipanggil")
        self.assertIsNotNone(
            self.diterima[0],
            "lintasan pertama halaman 8 tidak menerima petunjuk apa pun",
        )
        self.assertIn("Mutu Baku", self.diterima[0])
        kabar("           halaman 8 menerima petunjuk tabel dari halaman 7")

    def test_lupa_mengoper_petunjuk_membuat_halaman_lanjutan_telanjang(self):
        """
        Sisi sebaliknya, dan alasan uji ini ada: melewatkan nilai kembalian
        tidak menimbulkan galat, hanya membuat halaman lanjutan kehilangan
        aturan formatnya. Tanpa uji dua arah, kesalahan ini tak terlihat.
        """
        self.teks_berikut = self.TEKS_LANJUTAN
        self.diterima.clear()
        self.pp.ekstrak_satu_halaman(str(self.PDF), 8, None)   # petunjuk TIDAK dioper
        self.assertIsNone(self.diterima[0])

    def test_halaman_lanjutan_tidak_diberi_petunjuk_kepala(self):
        """
        Halaman tanpa kepala yang diberi tahu bahwa 'Nama SOP' PASTI ada akan
        mengarang satu. Sudah terjadi: halaman 8 dan 10 menghasilkan
        'Nomor SOP: 001' yang tidak ada di PDF-nya.
        """
        _, petunjuk = self.pp.ekstrak_satu_halaman(str(self.PDF), 7, None)

        self.diterima.clear()
        self.teks_berikut = self.TEKS_LANJUTAN
        self.pp.ekstrak_satu_halaman(str(self.PDF), 8, petunjuk)

        for dikirim in self.diterima:
            self.assertNotIn("PASTI ada", dikirim or "")

    def test_halaman_kepala_dibaca_ulang_dengan_petunjuk_kepala(self):
        """Halaman yang kepalanya memang ada justru HARUS menerimanya."""
        self.pp.ekstrak_satu_halaman(str(self.PDF), 7, None)
        self.assertTrue(
            any("PASTI ada" in (d or "") for d in self.diterima),
            "halaman berkepala tidak pernah menerima petunjuk kepala",
        )

    def test_halaman_di_luar_jangkauan_ditolak(self):
        with self.assertRaises(ValueError):
            self.pp.ekstrak_satu_halaman(str(self.PDF), 999, None)

    def test_hasil_sama_dengan_jalur_seluruh_dokumen(self):
        """
        Dua jalur, satu logika. Kalau keduanya menyimpang, ekstraksi bertahap
        diam-diam menghasilkan korpus yang berbeda dari ekstraksi sekali jalan.
        """
        self.teks_berikut = self.TEKS_KEPALA
        satu, _ = self.pp.ekstrak_satu_halaman(str(self.PDF), 7, None)
        semua = self.pp.extract_text(str(self.PDF), page_num=6)   # 0-indeks
        self.assertEqual(satu, semua[0]["text"])


# ══════════════════════════════════════════════════════════════════
# TAHAP 0b — Penyimpanan:  memori dan MySQL harus sepakat
# ══════════════════════════════════════════════════════════════════
class Tahap0Penyimpanan(unittest.TestCase):
    """
    Dua penyimpanan, satu alur. `PenyimpananMemori` dipakai uji dan CLI,
    `PenyimpananMySQL` dipakai produksi — dan `ekstrak_bertahap` memanggil
    keduanya lewat antarmuka yang sama.

    Kalau salah satu kehilangan sebuah metode, yang gagal bukan uji melainkan
    produksi, dengan `AttributeError` di tengah OCR yang sudah berjalan
    setengah jam. Uji ini menangkapnya sebelum itu.

    SQL-nya sendiri TIDAK diuji di sini — ia memakai `ON DUPLICATE KEY UPDATE`
    yang khas MySQL, dan menguji itu menuntut MySQL yang hidup. Yang dijamin di
    sini adalah bentuk antarmukanya, bukan kebenaran querynya.
    """

    def test_kedua_penyimpanan_punya_metode_yang_sama(self):
        from app.services import ekstraksi_bertahap as eb

        wajib = [
            "halaman_tersimpan", "simpan_halaman", "jeda_diminta",
            "catat_status", "baca_petunjuk", "simpan_petunjuk",
        ]
        for nama in wajib:
            with self.subTest(metode=nama):
                self.assertTrue(hasattr(eb.PenyimpananMemori, nama),
                                f"PenyimpananMemori kehilangan {nama}()")
                self.assertTrue(hasattr(eb.PenyimpananMySQL, nama),
                                f"PenyimpananMySQL kehilangan {nama}()")

    def test_keduanya_menyediakan_teks_terkumpul(self):
        """Dipakai tahap potong/embed untuk membaca hasil ekstraksi."""
        from app.services import ekstraksi_bertahap as eb

        for kelas in (eb.PenyimpananMemori, eb.PenyimpananMySQL):
            with self.subTest(kelas=kelas.__name__):
                self.assertTrue(hasattr(kelas, "teks_terkumpul"))

    def test_catatan_format_bertahan_melewati_jeda(self):
        """
        Inti kenapa catatan format ikut DISIMPAN, bukan cuma dioper antar
        panggilan: worker yang dijalankan ulang setelah jeda memulai dari
        memori kosong. Kalau catatan itu tidak tersimpan, halaman lanjutan
        kehilangan aturan formatnya tanpa galat apa pun.
        """
        from app.services import ekstraksi_bertahap as eb

        simpanan = eb.PenyimpananMemori()
        diterima: list[str | None] = []

        def ocr(nomor: int, petunjuk: str | None):
            diterima.append(petunjuk)
            return f"hal {nomor}", "format-sop"

        # Putaran pertama: dua halaman, lalu dijeda.
        eb.ekstrak_bertahap(1, 4, ocr, simpanan, maks_halaman=2)
        self.assertEqual(simpanan.baca_petunjuk(1), "format-sop")

        # Putaran kedua meniru worker baru — hanya penyimpanan yang tersisa.
        diterima.clear()
        eb.ekstrak_bertahap(1, 4, ocr, simpanan)
        self.assertEqual(
            diterima[0], "format-sop",
            "halaman 3 memulai dengan catatan kosong setelah jeda",
        )

    def test_status_menunggu_koreksi_terdaftar(self):
        """Dev 2 menangani status dari daftar ini; yang tidak terdaftar tak tertangani."""
        from app.services import ekstraksi_bertahap as eb

        self.assertIn(eb.STATUS_MENUNGGU_KOREKSI, eb.SEMUA_STATUS)
        self.assertEqual(len(eb.SEMUA_STATUS), len(set(eb.SEMUA_STATUS)))


# ══════════════════════════════════════════════════════════════════
# TAHAP 5 — Endpoint:  kendali alur lewat HTTP
# ══════════════════════════════════════════════════════════════════
class Tahap5Endpoint(unittest.TestCase):
    """
    Delapan endpoint yang dipakai Dev 2. Basis data dan Celery diganti tiruan —
    yang diuji di sini adalah kontraknya: kode status, bentuk balasan, dan
    penolakan yang harus terjadi.

    Kontrak inilah yang dibangun Dev 2 di atasnya. Ia harus stabil lebih dulu
    daripada isinya, karena mengubahnya belakangan berarti mengubah pekerjaan
    orang lain yang sudah jalan.
    """

    @classmethod
    def setUpClass(cls):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.routers import documents, ekstraksi
        from app.services import ekstraksi_bertahap as eb

        cls.eb = eb
        cls.mod = ekstraksi
        cls.dok_asli = ekstraksi.get_document_by_id
        cls.simpanan_asli = ekstraksi._penyimpanan

        ekstraksi.get_document_by_id = lambda i: (
            {"id": i, "file_path": "berkas.pdf"} if i == 1 else None
        )

        app = FastAPI()
        app.include_router(ekstraksi.router)
        app.dependency_overrides[documents.verify_token] = lambda: "uji"
        cls.klien = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.mod.get_document_by_id = cls.dok_asli
        cls.mod._penyimpanan = cls.simpanan_asli

    def setUp(self):
        self.simpanan = self.eb.PenyimpananMemori()
        self.simpanan.mulai_job = lambda *a, **k: None
        self.simpanan.keadaan = lambda i: self._keadaan
        self._keadaan = {
            "document_id": 1, "status": self.eb.STATUS_MENUNGGU_KOREKSI,
            "jeda_diminta": False, "halaman_total": 3,
            "halaman_selesai": 3, "persen": 100, "pesan": None,
        }
        self.mod._penyimpanan = lambda: self.simpanan

        self.diantrekan: list[tuple] = []

        class TugasPalsu:
            def __init__(self, catat):
                self._catat = catat

            def delay(self, *a, **k):
                self._catat.append(a)

        import app.tasks.ekstraksi as tugas
        self.tugas = tugas
        self._ekstrak_asli = tugas.ekstrak_dokumen_task
        self._potong_asli = tugas.potong_dan_embed_task
        tugas.ekstrak_dokumen_task = TugasPalsu(self.diantrekan)
        tugas.potong_dan_embed_task = TugasPalsu(self.diantrekan)

    def tearDown(self):
        self.tugas.ekstrak_dokumen_task = self._ekstrak_asli
        self.tugas.potong_dan_embed_task = self._potong_asli

    # ── mulai / lanjut ──────────────────────────────────────────

    def test_mulai_ekstraksi_mengantrekan_tugas(self):
        r = self.klien.post("/api/docs/1/ekstraksi", json={"maks_halaman": 5})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["status"], self.eb.STATUS_ANTRE)
        self.assertEqual(len(self.diantrekan), 1)
        kabar(f"\n  TAHAP 5 — mulai/lanjut mengantrekan: {self.diantrekan[0]}")

    def test_dokumen_tidak_ada_404(self):
        for metode, jalur in (
            ("get", "/api/docs/9/ekstraksi"),
            ("post", "/api/docs/9/ekstraksi/jeda"),
            ("get", "/api/docs/9/halaman"),
            ("get", "/api/docs/9/potongan"),
            ("post", "/api/docs/9/simpan"),
        ):
            with self.subTest(jalur=jalur):
                r = getattr(self.klien, metode)(jalur)
                self.assertEqual(r.status_code, 404)

    # ── jeda ────────────────────────────────────────────────────

    def test_jeda_menyalakan_bendera(self):
        r = self.klien.post("/api/docs/1/ekstraksi/jeda")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.json()["jeda_diminta"])
        self.assertTrue(self.simpanan.jeda_diminta(1))

    # ── status ──────────────────────────────────────────────────

    def test_belum_pernah_diekstrak_bukan_404(self):
        """
        Dokumen ada tapi belum pernah diekstrak adalah keadaan AWAL, bukan
        galat. Mengembalikan 404 memaksa Dev 2 menangani dua cabang untuk satu
        hal yang sama.
        """
        self.simpanan.keadaan = lambda i: None
        r = self.klien.get("/api/docs/1/ekstraksi")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], self.eb.STATUS_ANTRE)
        self.assertEqual(r.json()["persen"], 0)

    def test_status_membawa_medan_yang_dipakai_antarmuka(self):
        r = self.klien.get("/api/docs/1/ekstraksi")
        for medan in ("status", "jeda_diminta", "halaman_total",
                      "halaman_selesai", "persen", "pesan"):
            with self.subTest(medan=medan):
                self.assertIn(medan, r.json())

    # ── koreksi ─────────────────────────────────────────────────

    def test_koreksi_halaman_tersimpan(self):
        r = self.klien.put("/api/docs/1/halaman/2", json={"text": "teks yang sudah benar"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.simpanan.halaman[1][2], "teks yang sudah benar")

    def test_koreksi_kosong_ditolak(self):
        """Halaman kosong lenyap dari korpus tanpa galat — tolak lebih awal."""
        for isi in ("", "   ", "\n\n"):
            with self.subTest(isi=repr(isi)):
                r = self.klien.put("/api/docs/1/halaman/2", json={"text": isi})
                self.assertEqual(r.status_code, 400)

    def test_triase_hanya_halaman_mencurigakan(self):
        self.simpanan.simpan_halaman(1, 1, "Nomor SOP: 9/X/2025\nNama SOP: A\nNIP. 123456789")
        self.simpanan.simpan_halaman(1, 2, "Nomor SOP: 6/X/2025\nNama SOP: B")   # NIP hilang
        self.simpanan.simpan_halaman(1, 3, "Halaman biasa tanpa formulir apa pun.")

        r = self.klien.get("/api/docs/1/halaman?perlu_diperiksa=1")
        self.assertEqual(r.status_code, 200)
        curiga = r.json()["halaman"]
        self.assertEqual([h["page_number"] for h in curiga], [2])
        self.assertIn("NIP", curiga[0]["alasan"])
        kabar(f"           triase menandai halaman {[h['page_number'] for h in curiga]}")

    # ── simpan ke korpus ────────────────────────────────────────

    def test_simpan_saat_masih_berjalan_ditolak(self):
        self._keadaan = {**self._keadaan, "status": self.eb.STATUS_BERJALAN}
        r = self.klien.post("/api/docs/1/simpan")
        self.assertEqual(r.status_code, 409)

    def test_simpan_tanpa_halaman_ditolak(self):
        self._keadaan = {**self._keadaan, "halaman_selesai": 0}
        r = self.klien.post("/api/docs/1/simpan")
        self.assertEqual(r.status_code, 409)

    def test_simpan_setelah_koreksi_diantrekan(self):
        r = self.klien.post("/api/docs/1/simpan")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(len(self.diantrekan), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
