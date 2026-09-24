"""
Ekstraksi halaman demi halaman yang bisa dijeda dan dilanjutkan.

Masalah yang dipecahkan: `pdf_processor.extract_text()` mengerjakan SELURUH
dokumen dalam satu panggilan. Untuk 171 halaman pindaian itu berjam-jam, dan
selama itu tidak ada cara menghentikannya tanpa membuang seluruh pekerjaan —
proses mati di halaman 168 berarti mengulang dari halaman 1.

Rancangannya bertumpu pada tiga keputusan:

1. **Simpan tiap halaman SEBELUM lanjut.** Kemajuan yang sudah dibayar dengan
   waktu OCR tidak boleh hilang karena apa pun — jeda, mati listrik, worker
   dibunuh. Semuanya jadi setara: yang tersimpan tetap tersimpan.

2. **Jeda itu KOOPERATIF, bukan pembunuhan proses.** Satu panggilan model
   vision berlangsung 20-60 detik dan tidak bisa dipotong di tengah tanpa
   menyisakan halaman separuh. Jadi permintaan jeda diperiksa DI ANTARA
   halaman: halaman yang sedang berjalan diselesaikan dulu, baru berhenti.

3. **Sinyal jeda lewat penyimpanan bersama, bukan variabel di memori.**
   Permintaan jeda datang dari permintaan web di proses lain — bukan proses
   yang sedang meng-OCR. Bendera di memori tidak akan pernah terlihat oleh
   worker. Karena MySQL sudah dipakai bersama Laravel, di situlah benderanya.

Yang SENGAJA tidak dilakukan: memotong dan meng-embed per halaman. Dua
mekanisme di layanan ini melintasi batas halaman —
`pdf_processor.perbaiki_penanda_daftar()` memulihkan penanda daftar dengan
melihat halaman sebelumnya (penerus `ggg` adalah `hhh`), dan pewarisan konteks
membuat halaman lanjutan memakai label halaman kepalanya. Memotong halaman 4
sebelum halaman 3 selesai berarti keduanya kehilangan pendahulunya. Pemotongan
karena itu menunggu SELURUH halaman terkumpul.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Keadaan yang dilihat pengguna di web. Sengaja sedikit dan tidak tumpang
# tindih; tiap tambahan keadaan adalah satu cabang baru yang harus ditangani
# Dev 2 di antarmuka.
STATUS_ANTRE = "antre"
STATUS_BERJALAN = "berjalan"
STATUS_JEDA = "jeda"
# Keadaan DIAM: semua halaman sudah terekstrak, sistem tidak mengerjakan apa
# pun, menunggu admin menyatakan koreksinya beres. Hasil OCR dokumen pindaian
# tidak layak masuk korpus tanpa diperiksa mata manusia.
STATUS_MENUNGGU_KOREKSI = "menunggu_koreksi"
STATUS_SELESAI = "selesai"
STATUS_GAGAL = "gagal"

SEMUA_STATUS = (
    STATUS_ANTRE,
    STATUS_BERJALAN,
    STATUS_JEDA,
    STATUS_MENUNGGU_KOREKSI,
    STATUS_SELESAI,
    STATUS_GAGAL,
)

# Batas interval halaman untuk membersihkan prompt/KV cache Ollama di RAM.
# Angka 12 halaman (~1.9 GB cache) memaksimalkan pemakaian RAM tanpa menyentuh
# batas kritis (thrashing/OOM).
_FLUSH_CACHE_INTERVAL = 12


def flush_ollama_cache(model_name: str | None = None) -> None:
    """
    Membebaskan akumulasi prompt/KV cache Ollama dari RAM/VRAM.

    Ollama menimbun prompt cache per halaman hingga batas 8 GB. Pada batch
    ekstraksi gambar, cache halaman lama tidak pernah terpakai lagi.
    Mengirim keep_alive: 0 mengosongkan timbunan cache tersebut dan menjaga
    kecepatan inferensi stabil di ~11-12 t/s.
    """
    try:
        import requests
        from app.config import settings
        from app.services.pdf_processor import resolve_vision_model

        target_model = resolve_vision_model(model_name)
        requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={"model": target_model, "keep_alive": 0},
            timeout=5,
        )
        logger.info("Prompt cache Ollama (%s) berhasil dibersihkan (VRAM/RAM dilepas).", target_model)
    except Exception as e:
        logger.warning("Gagal flush cache Ollama: %s", e)



class Penyimpanan(Protocol):
    """
    Antarmuka penyimpanan kemajuan.

    Dipisah sebagai protokol supaya inti alurnya bisa diuji tanpa MySQL. Bagian
    yang paling rawan salah di sini bukan SQL-nya, melainkan urutan
    simpan-lalu-periksa — dan justru itu yang tidak akan pernah teruji kalau
    ujinya menuntut basis data hidup.
    """

    def dokumen_ada(self, document_id: int) -> bool: ...

    def halaman_tersimpan(self, document_id: int) -> set[int]: ...

    def simpan_halaman(self, document_id: int, nomor: int, teks: str) -> bool: ...

    def jeda_diminta(self, document_id: int) -> bool: ...

    def catat_status(self, document_id: int, status: str, pesan: str | None = None) -> None: ...

    # Catatan format yang dibawa antar halaman (lihat pdf_processor.
    # ekstrak_satu_halaman). Ikut disimpan, bukan sekadar dioper antar
    # panggilan: tanpa itu ia lenyap saat pekerjaan dijeda dan worker
    # dijalankan ulang, lalu halaman lanjutan kehilangan aturan formatnya
    # tanpa galat apa pun.
    def baca_petunjuk(self, document_id: int) -> str | None: ...

    def simpan_petunjuk(self, document_id: int, petunjuk: str | None) -> None: ...

    def batalkan_jeda(self, document_id: int) -> None: ...

    def reset_ekstraksi(self, document_id: int) -> None: ...


@dataclass
class Kemajuan:
    """Ringkasan satu putaran ekstraksi, dikembalikan ke pemanggil."""

    document_id: int
    status: str
    halaman_total: int
    halaman_selesai: int
    halaman_diproses_kali_ini: list[int] = field(default_factory=list)
    detik: float = 0.0
    pesan: str | None = None

    @property
    def persen(self) -> int:
        if not self.halaman_total:
            return 0
        return round(self.halaman_selesai / self.halaman_total * 100)

    @property
    def perkiraan_sisa_detik(self) -> float | None:
        """
        Perkiraan berdasarkan halaman yang BARU SAJA dikerjakan, bukan rata-rata
        seluruh riwayat. Kecepatan OCR berubah menurut kepadatan halaman dan
        beban mesin; rata-rata riwayat panjang menyembunyikan perubahan itu.
        """
        jumlah = len(self.halaman_diproses_kali_ini)
        if not jumlah or not self.detik:
            return None
        sisa = self.halaman_total - self.halaman_selesai
        return (self.detik / jumlah) * sisa


def ekstrak_bertahap(
    document_id: int,
    halaman_total: int,
    ocr_satu_halaman: Callable[[int, str | None], tuple[str, str | None]],
    penyimpanan: Penyimpanan,
    *,
    maks_halaman: int | None = None,
) -> Kemajuan:
    """
    Kerjakan halaman yang belum tersimpan, satu per satu, sampai selesai atau dijeda.

    Argumen:
        halaman_total: jumlah halaman dokumen. Dipakai untuk persentase dan
            untuk tahu kapan pekerjaan benar-benar tuntas.
        ocr_satu_halaman: fungsi (nomor, catatan) -> (teks, catatan_baru) untuk
            SATU halaman (1-indeks). Disuntikkan, bukan dipanggil langsung,
            supaya alur ini bisa diuji tanpa Ollama — dan supaya pemanggil
            bebas memilih jalur ekstraksi.
            Catatan formatnya dibaca dari penyimpanan sebelum halaman pertama
            dan disimpan kembali sesudah tiap halaman, sehingga ia bertahan
            melewati jeda maupun worker yang mati di tengah jalan.
        maks_halaman: batas halaman per putaran. Berguna bila pemanggil ingin
            memotong pekerjaan jadi beberapa tugas Celery pendek alih-alih satu
            tugas panjang.

    Melanjutkan otomatis: halaman yang sudah tersimpan dilewati, jadi memanggil
    fungsi ini berulang kali aman dan selalu meneruskan dari yang terakhir.
    """
    mulai = time.perf_counter()

    # Periksa apakah dokumen masih ada di basis data
    if not penyimpanan.dokumen_ada(document_id):
        logger.info("Dokumen %d tidak ditemukan di basis data saat mulai ekstraksi bertahap.", document_id)
        return Kemajuan(
            document_id, STATUS_GAGAL, halaman_total, 0,
            pesan="Dokumen tidak ditemukan di basis data.",
        )

    sudah = penyimpanan.halaman_tersimpan(document_id)
    tersisa = [n for n in range(1, halaman_total + 1) if n not in sudah]

    if not tersisa:
        penyimpanan.catat_status(document_id, STATUS_SELESAI)
        return Kemajuan(document_id, STATUS_SELESAI, halaman_total, halaman_total)

    # Diperiksa SEBELUM halaman pertama juga: pengguna bisa menekan jeda saat
    # tugas masih mengantre di Celery, dan permintaan itu harus tetap dihormati.
    if penyimpanan.jeda_diminta(document_id):
        penyimpanan.catat_status(document_id, STATUS_JEDA)
        return Kemajuan(document_id, STATUS_JEDA, halaman_total, len(sudah))

    penyimpanan.catat_status(document_id, STATUS_BERJALAN)
    petunjuk = penyimpanan.baca_petunjuk(document_id)
    diproses: list[int] = []

    for nomor in tersisa:
        if maks_halaman is not None and len(diproses) >= maks_halaman:
            break

        # 1. Periksa apakah dokumen masih ada sebelum membuang 20-60 detik waktu inferensi vision
        if not penyimpanan.dokumen_ada(document_id):
            logger.info("Dokumen %d telah dihapus dari sistem. Menghentikan ekstraksi bertahap.", document_id)
            flush_ollama_cache()
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
                pesan="Dokumen telah dihapus dari sistem.",
            )

        # 2. Periksa permintaan jeda SEBELUM memulai OCR halaman berikutnya
        if penyimpanan.jeda_diminta(document_id):
            penyimpanan.catat_status(document_id, STATUS_JEDA)
            penyimpanan.batalkan_jeda(document_id)
            flush_ollama_cache()
            return Kemajuan(
                document_id, STATUS_JEDA, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
            )

        try:
            teks, petunjuk = ocr_satu_halaman(nomor, petunjuk)
        except Exception as e:  # noqa: BLE001 - dicatat sebagai status, bukan ditelan
            # Jika dokumen telah dihapus saat inferensi berlangsung, keluar secara bersih
            if not penyimpanan.dokumen_ada(document_id):
                logger.info("Dokumen %d telah dihapus saat ekstraksi halaman %d. Ekstraksi dihentikan.", document_id, nomor)
                flush_ollama_cache()
                return Kemajuan(
                    document_id, STATUS_GAGAL, halaman_total,
                    len(sudah) + len(diproses), diproses,
                    time.perf_counter() - mulai,
                    pesan="Dokumen telah dihapus dari sistem.",
                )
            pesan = f"Halaman {nomor} gagal: {type(e).__name__}: {e}"
            logger.error(pesan)
            penyimpanan.catat_status(document_id, STATUS_GAGAL, pesan)
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai, pesan,
            )

        # 3. Disimpan SEBELUM apa pun yang lain. Kalau dokumen dihapus saat proses berjalan, simpan_halaman mengembalikan False
        tersimpan = penyimpanan.simpan_halaman(document_id, nomor, teks)
        if not tersimpan:
            logger.info("Dokumen %d telah dihapus sebelum menyimpan halaman %d. Menghentikan ekstraksi.", document_id, nomor)
            flush_ollama_cache()
            return Kemajuan(
                document_id, STATUS_GAGAL, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
                pesan="Dokumen telah dihapus dari sistem.",
            )

        penyimpanan.simpan_petunjuk(document_id, petunjuk)
        diproses.append(nomor)
        logger.info(
            "Dokumen %d: halaman %d tersimpan (%d/%d)",
            document_id, nomor, len(sudah) + len(diproses), halaman_total,
        )

        # Bersihkan timbunan prompt cache Ollama setiap 12 halaman agar RAM tidak bocor
        if len(diproses) % _FLUSH_CACHE_INTERVAL == 0:
            flush_ollama_cache()

        # Baru sesudah tersimpan, periksa permintaan jeda. Urutannya penting:
        # memeriksa lebih dulu berarti membuang halaman yang baru saja dibayar
        # dengan puluhan detik OCR.
        if penyimpanan.jeda_diminta(document_id):
            penyimpanan.catat_status(document_id, STATUS_JEDA)
            penyimpanan.batalkan_jeda(document_id)
            flush_ollama_cache()
            return Kemajuan(
                document_id, STATUS_JEDA, halaman_total,
                len(sudah) + len(diproses), diproses,
                time.perf_counter() - mulai,
            )

    selesai = len(sudah) + len(diproses)
    status = STATUS_SELESAI if selesai >= halaman_total else STATUS_BERJALAN
    penyimpanan.catat_status(document_id, status)
    flush_ollama_cache()

    return Kemajuan(
        document_id, status, halaman_total, selesai, diproses,
        time.perf_counter() - mulai,
    )


class PenyimpananMemori:
    """
    Penyimpanan dalam memori — untuk pengujian dan pemakaian CLI satu proses.

    Bukan untuk produksi: bendera jeda di sini tidak akan pernah terlihat oleh
    proses lain, dan itulah persis masalah yang `PenyimpananMySQL` pecahkan.
    """

    def __init__(self) -> None:
        self.halaman: dict[int, dict[int, str]] = {}
        self.status: dict[int, tuple[str, str | None]] = {}
        self.jeda: set[int] = set()
        self.petunjuk: dict[int, str | None] = {}
        self.dokumen_valid: set[int] = set()

    def dokumen_ada(self, document_id: int) -> bool:
        if not self.dokumen_valid:
            return True
        return document_id in self.dokumen_valid

    def halaman_tersimpan(self, document_id: int) -> set[int]:
        return set(self.halaman.get(document_id, {}))

    def simpan_halaman(self, document_id: int, nomor: int, teks: str) -> bool:
        self.halaman.setdefault(document_id, {})[nomor] = teks
        return True

    def jeda_diminta(self, document_id: int) -> bool:
        return document_id in self.jeda

    def catat_status(self, document_id: int, status: str, pesan: str | None = None) -> None:
        self.status[document_id] = (status, pesan)

    def baca_petunjuk(self, document_id: int) -> str | None:
        return self.petunjuk.get(document_id)

    def simpan_petunjuk(self, document_id: int, petunjuk: str | None) -> None:
        self.petunjuk[document_id] = petunjuk

    # -- kendali, dipakai oleh penguji dan CLI --------------------------------

    def minta_jeda(self, document_id: int) -> None:
        self.jeda.add(document_id)

    def batalkan_jeda(self, document_id: int) -> None:
        self.jeda.discard(document_id)

    def reset_ekstraksi(self, document_id: int) -> None:
        self.halaman.pop(document_id, None)
        self.status.pop(document_id, None)
        self.jeda.discard(document_id)
        self.petunjuk.pop(document_id, None)
        self.dokumen_valid.discard(document_id)

    def teks_terkumpul(self, document_id: int) -> list[dict]:
        """Halaman tersimpan dalam bentuk yang diterima chunk_text_hierarchical."""
        halaman = self.halaman.get(document_id, {})
        return [
            {"page_number": n, "text": halaman[n]}
            for n in sorted(halaman)
        ]

class PenyimpananMySQL:
    """
    Penyimpanan kemajuan di MySQL — basis data yang sama dengan Laravel.

    Inilah versi yang membuat jeda benar-benar bekerja. Permintaan jeda datang
    dari permintaan web di proses lain, bukan proses yang sedang meng-OCR;
    bendera di memori tidak akan pernah terlihat oleh worker. Karena tabelnya
    dipakai bersama, Laravel bahkan boleh menulis benderanya langsung tanpa
    memanggil layanan Python sama sekali — satu titik gagal hilang, dan tombol
    jeda tetap bekerja walau layanan AI sedang sibuk.

    Dua tabel yang diperlukan:

        CREATE TABLE ekstraksi_job (
          document_id     BIGINT PRIMARY KEY,
          status          ENUM('antre','berjalan','jeda',
                               'menunggu_koreksi','selesai','gagal') NOT NULL,
          jeda_diminta    TINYINT(1) NOT NULL DEFAULT 0,
          halaman_total   INT NOT NULL,
          halaman_selesai INT NOT NULL DEFAULT 0,
          petunjuk_format TEXT NULL,
          pesan           TEXT NULL,
          updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP
        );

        CREATE TABLE ekstraksi_halaman (
          document_id  BIGINT NOT NULL,
          page_number  INT NOT NULL,
          text         LONGTEXT NOT NULL,
          diperiksa    TINYINT(1) NOT NULL DEFAULT 0,
          created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (document_id, page_number)
        );

    `PRIMARY KEY (document_id, page_number)` bukan formalitas: dengan
    ON DUPLICATE KEY UPDATE, melanjutkan ekstraksi tidak pernah bisa
    menggandakan halaman — walau tugas Celery-nya kebetulan berjalan dua kali.
    """

    def __init__(self, engine=None) -> None:
        # Engine boleh disuntikkan supaya kelas ini bisa diuji dengan SQLite
        # di memori tanpa MySQL hidup.
        if engine is None:
            from app.database import get_engine

            engine = get_engine()
        self._engine = engine

    # ── dibaca alur ekstraksi ────────────────────────────────────

    def dokumen_ada(self, document_id: int) -> bool:
        """Periksa apakah dokumen masih ada di tabel documents."""
        sql = text("SELECT 1 FROM documents WHERE id = :id")
        try:
            with self._engine.connect() as conn:
                return conn.execute(sql, {"id": document_id}).scalar() is not None
        except Exception as e:
            logger.warning("Gagal cek keberadaan dokumen %d: %s", document_id, e)
            return False

    def halaman_tersimpan(self, document_id: int) -> set[int]:
        sql = text(
            "SELECT page_number FROM ekstraksi_halaman "
            "WHERE document_id = :id AND LENGTH(TRIM(COALESCE(text, ''))) > 0"
        )
        try:
            with self._engine.connect() as conn:
                return {baris[0] for baris in conn.execute(sql, {"id": document_id})}
        except Exception as e:
            logger.warning("Gagal membaca halaman tersimpan dokumen %d: %s", document_id, e)
            return set()

    def jeda_diminta(self, document_id: int) -> bool:
        sql = text(
            "SELECT jeda_diminta, status FROM ekstraksi_job WHERE document_id = :id"
        )
        try:
            with self._engine.connect() as conn:
                baris = conn.execute(sql, {"id": document_id}).fetchone()
            if not baris:
                return False
            is_requested = bool(baris[0])
            status_str = str(baris[1]).lower() if baris[1] else ""
            return is_requested or status_str in ("jeda", "paused")
        except Exception as e:
            logger.warning("Gagal cek jeda_diminta dokumen %d: %s", document_id, e)
            return False

    def baca_petunjuk(self, document_id: int) -> str | None:
        sql = text(
            "SELECT petunjuk_format FROM ekstraksi_job WHERE document_id = :id"
        )
        try:
            with self._engine.connect() as conn:
                baris = conn.execute(sql, {"id": document_id}).fetchone()
            return baris[0] if baris else None
        except Exception as e:
            logger.warning("Gagal membaca petunjuk format dokumen %d: %s", document_id, e)
            return None

    # ── ditulis alur ekstraksi ───────────────────────────────────

    def simpan_halaman(self, document_id: int, nomor: int, teks: str) -> bool:
        """
        Menulis ulang halaman yang sama aman: kunci utamanya (document_id,
        page_number), jadi mengulang tugas tidak menggandakan baris.

        `diperiksa` sengaja TIDAK ikut ditimpa di sini. Kolom itu milik
        korektor; kalau ekstraksi ulang meresetnya diam-diam, pekerjaan
        memeriksa ratusan halaman bisa hilang tanpa ada yang menyadarinya.

        Mengembalikan True jika berhasil disimpan, False jika dokumen sudah
        dihapus dari basis data (Foreign Key Constraint 1452).
        """
        sql = text(
            "INSERT INTO ekstraksi_halaman (document_id, page_number, text) "
            "VALUES (:id, :nomor, :teks) "
            "ON DUPLICATE KEY UPDATE text = VALUES(text)"
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"id": document_id, "nomor": nomor, "teks": teks})
            return True
        except Exception as e:
            err_str = str(e).lower()
            if "foreign key constraint" in err_str or "1452" in err_str:
                logger.warning(
                    "Dokumen %d telah dihapus dari basis data saat menyimpan halaman %d. Operasi dibatalkan secara bersih.",
                    document_id, nomor,
                )
                return False
            logger.exception("Gagal menyimpan halaman %d untuk dokumen %d", nomor, document_id)
            raise

    def simpan_petunjuk(self, document_id: int, petunjuk: str | None) -> None:
        sql = text(
            "UPDATE ekstraksi_job SET petunjuk_format = :petunjuk "
            "WHERE document_id = :id"
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"id": document_id, "petunjuk": petunjuk})
        except Exception as e:
            logger.warning("Gagal menyimpan petunjuk dokumen %d: %s", document_id, e)

    def catat_status(
        self, document_id: int, status: str, pesan: str | None = None
    ) -> None:
        """
        `halaman_selesai` dihitung ulang dari tabel halaman, bukan dinaikkan
        satu per satu. Penghitung yang dinaikkan sendiri akan menyimpang dari
        kenyataan begitu ada tugas yang mengulang atau gagal di tengah — dan
        angka kemajuan yang bohong lebih buruk daripada tidak ada angka.
        """
        sql = text(
            "UPDATE ekstraksi_job SET "
            "  status = :status, "
            "  pesan = :pesan, "
            "  halaman_selesai = ("
            "    SELECT COUNT(*) FROM ekstraksi_halaman "
            "    WHERE document_id = :id AND LENGTH(TRIM(COALESCE(text, ''))) > 0"
            "  ) "
            "WHERE document_id = :id"
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"id": document_id, "status": status, "pesan": pesan})
        except Exception as e:
            logger.warning("Gagal mencatat status '%s' dokumen %d: %s", status, document_id, e)

    # ── dipakai endpoint & tugas Celery ──────────────────────────

    def mulai_job(self, document_id: int, halaman_total: int) -> None:
        """
        Buat baris job bila belum ada, dan cabut permintaan jeda yang lama.

        Pencabutan itu penting: 'lanjutkan' dan 'mulai' adalah endpoint yang
        sama, dan bendera jeda dari putaran sebelumnya masih menyala. Tanpa
        dicabut, permintaan lanjut akan langsung berhenti lagi di halaman
        pertama — terlihat seperti tombolnya tidak berfungsi.
        """
        sql = text(
            "INSERT INTO ekstraksi_job "
            "  (document_id, status, jeda_diminta, halaman_total) "
            "VALUES (:id, :status, 0, :total) "
            "ON DUPLICATE KEY UPDATE "
            "  jeda_diminta = 0, status = :status, halaman_total = :total"
        )
        with self._engine.begin() as conn:
            conn.execute(
                sql,
                {"id": document_id, "status": STATUS_ANTRE, "total": halaman_total},
            )

    def minta_jeda(self, document_id: int) -> None:
        """
        Setel jeda pada ekstraksi.
        Tandai jeda_diminta = 1 pada ekstraksi_job agar worker OCR berhenti di batas halaman.
        Bila semua halaman sudah terkumpul (halaman_selesai >= halaman_total),
        langsung alihkan ke 'menunggu_koreksi'.
        """
        sql = text(
            "UPDATE ekstraksi_job SET "
            "  jeda_diminta = CASE "
            "    WHEN halaman_selesai >= halaman_total AND halaman_total > 0 THEN 0 "
            "    ELSE 1 "
            "  END, "
            "  status = CASE "
            "    WHEN halaman_selesai >= halaman_total AND halaman_total > 0 THEN 'menunggu_koreksi' "
            "    ELSE status "
            "  END "
            "WHERE document_id = :id"
        )
        with self._engine.begin() as conn:
            conn.execute(sql, {"id": document_id})

    def batalkan_jeda(self, document_id: int) -> None:
        """Cabut atau reset bendera jeda_diminta kembali ke 0."""
        sql = text(
            "UPDATE ekstraksi_job SET jeda_diminta = 0 WHERE document_id = :id"
        )
        with self._engine.begin() as conn:
            conn.execute(sql, {"id": document_id})

    def catat_kemajuan_embed(
        self, document_id: int, status: str, persen: int, pesan: str | None = None
    ) -> None:
        """
        Catat kemajuan persentase (0-100%) dan pesan status tahapan embedding ke Redis dan ekstraksi_job.
        TIDAK merusak halaman_total atau halaman_selesai asli dokumen.
        """
        pct = max(0, min(100, int(persen)))

        # 1. Simpan ke Redis cache untuk polling modal real-time (0-100%)
        try:
            from app.services.session_memory import _get_redis
            r = _get_redis()
            if r:
                import json
                r.setex(
                    f"doc_embed_progress:{document_id}",
                    3600,
                    json.dumps({
                        "status": status,
                        "persen": pct,
                        "pesan": pesan or "",
                    }),
                )
        except Exception as e:
            logger.warning("Gagal menyimpan progress embed ke Redis untuk dokumen %d: %s", document_id, e)

        # 2. Update ekstraksi_job:
        # - Bila status 'selesai', perbarui status job ke 'selesai'.
        # - Bila status 'gagal', perbarui status job ke 'gagal'.
        # - JANGAN pernah ubah status menjadi 'berjalan' (karena itu milik proses OCR).
        # - JANGAN pernah ubah halaman_total = 100 atau halaman_selesai = persen.
        sql = text(
            "UPDATE ekstraksi_job SET "
            "  status = CASE "
            "    WHEN :status IN ('selesai', 'completed') THEN 'selesai' "
            "    WHEN :status IN ('gagal', 'failed') THEN 'gagal' "
            "    ELSE status "
            "  END, "
            "  pesan = :pesan "
            "WHERE document_id = :id"
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(sql, {"id": document_id, "status": status, "pesan": pesan})
        except Exception as e:
            logger.warning("Gagal mencatat status embed dokumen %d: %s", document_id, e)

    def keadaan(self, document_id: int) -> dict | None:
        """Ringkasan untuk endpoint status. None bila jobnya belum pernah ada."""
        sql = text(
            "SELECT status, jeda_diminta, halaman_total, halaman_selesai, pesan "
            "FROM ekstraksi_job WHERE document_id = :id"
        )
        with self._engine.connect() as conn:
            baris = conn.execute(sql, {"id": document_id}).mappings().fetchone()
        if baris is None:
            return None

        total = baris["halaman_total"] or 0
        selesai = baris["halaman_selesai"] or 0
        persen = round(selesai / total * 100) if total else 0

        # Cek jika ada kemajuan embedding aktif di Redis
        try:
            from app.services.session_memory import _get_redis
            r = _get_redis()
            if r:
                import json
                raw = r.get(f"doc_embed_progress:{document_id}")
                if raw:
                    info = json.loads(raw)
                    return {
                        "document_id": document_id,
                        "status": info.get("status", baris["status"]),
                        "jeda_diminta": bool(baris["jeda_diminta"]),
                        "halaman_total": total,
                        "halaman_selesai": selesai,
                        "persen": max(0, min(100, int(info.get("persen", persen)))),
                        "pesan": info.get("pesan", baris["pesan"]),
                    }
        except Exception:
            pass

        return {
            "document_id": document_id,
            "status": baris["status"],
            "jeda_diminta": bool(baris["jeda_diminta"]),
            "halaman_total": total,
            "halaman_selesai": selesai,
            "persen": max(0, min(100, persen)),
            "pesan": baris["pesan"],
        }

    def teks_terkumpul(self, document_id: int) -> list[dict]:
        """Halaman tersimpan dalam bentuk yang diterima chunk_text_hierarchical."""
        sql = text(
            "SELECT page_number, text FROM ekstraksi_halaman "
            "WHERE document_id = :id ORDER BY page_number"
        )
        with self._engine.connect() as conn:
            return [
                {"page_number": b[0], "text": b[1]}
                for b in conn.execute(sql, {"id": document_id})
            ]

    def reset_ekstraksi(self, document_id: int) -> None:
        """Hapus semua ekstraksi halaman dan data ekstraksi_job untuk document_id."""
        sql_halaman = text("DELETE FROM ekstraksi_halaman WHERE document_id = :id")
        sql_job = text("DELETE FROM ekstraksi_job WHERE document_id = :id")
        with self._engine.begin() as conn:
            conn.execute(sql_halaman, {"id": document_id})
            conn.execute(sql_job, {"id": document_id})
