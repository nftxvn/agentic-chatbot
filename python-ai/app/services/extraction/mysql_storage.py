"""Penyimpanan halaman/job MySQL dan progres embedding Redis untuk Laravel."""

import logging
from contextlib import contextmanager

from sqlalchemy import text

from app.services.extraction.contracts import STATUS_ANTRE
from app.services.document_operations import (
    CANCELLATION_MESSAGE,
    DocumentOperationCancelled,
    OperationGuard,
)

logger = logging.getLogger("app.services.ekstraksi_bertahap")

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

    def __init__(self, engine=None, *, operation_token: str | None = None) -> None:
        # Engine boleh disuntikkan supaya kelas ini bisa diuji dengan SQLite
        # di memori tanpa MySQL hidup.
        if engine is None:
            from app.database import get_engine

            engine = get_engine()
        self._engine = engine
        self._operation_token = operation_token

    @contextmanager
    def _write(self, document_id: int):
        """Use one connection for authorization, the row lock, and the mutation."""
        if self._operation_token is None:
            with self._engine.begin() as connection:
                yield connection
        else:
            with OperationGuard(document_id, self._operation_token, self._engine).write() as connection:
                yield connection

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
            with self._write(document_id) as conn:
                conn.execute(sql, {"id": document_id, "nomor": nomor, "teks": teks})
            return True
        except DocumentOperationCancelled:
            raise
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
            with self._write(document_id) as conn:
                conn.execute(sql, {"id": document_id, "petunjuk": petunjuk})
        except DocumentOperationCancelled:
            raise
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
            with self._write(document_id) as conn:
                conn.execute(sql, {"id": document_id, "status": status, "pesan": pesan})
        except DocumentOperationCancelled:
            raise
        except Exception as e:
            logger.warning("Gagal mencatat status '%s' dokumen %d: %s", status, document_id, e)

    # ── dipakai endpoint & tugas Celery ──────────────────────────

    def mulai_job(self, document_id: int, halaman_total: int) -> None:
        """
        Buat baris job bila belum ada. Jika baris sudah ada, pertahankan
        bendera jeda_diminta bila baru saja diset oleh pengguna saat job antre.
        """
        sql = text(
            "INSERT INTO ekstraksi_job "
            "  (document_id, status, jeda_diminta, halaman_total) "
            "VALUES (:id, :status, 0, :total) "
            "ON DUPLICATE KEY UPDATE "
            "  status = :status, halaman_total = :total"
        )
        with self._write(document_id) as conn:
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
        with self._write(document_id) as conn:
            conn.execute(sql, {"id": document_id})

    def batalkan_jeda(self, document_id: int) -> None:
        """Cabut atau reset bendera jeda_diminta kembali ke 0."""
        sql = text(
            "UPDATE ekstraksi_job SET jeda_diminta = 0 WHERE document_id = :id"
        )
        with self._write(document_id) as conn:
            conn.execute(sql, {"id": document_id})

    def catat_kemajuan_embed(
        self, document_id: int, status: str, persen: int, pesan: str | None = None
    ) -> None:
        """
        Catat kemajuan persentase (0-100%) dan pesan status tahapan embedding ke Redis dan ekstraksi_job.
        TIDAK merusak halaman_total atau halaman_selesai asli dokumen.
        """
        pct = max(0, min(100, int(persen)))

        # Update ekstraksi_job:
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
            # Guard before Redis too: an old worker must not publish progress
            # after cancellation/new generation. Redis is best-effort; SQL is
            # authoritative and both mutations remain inside the document lock.
            with self._write(document_id) as conn:
                try:
                    from app.services.session_memory import _get_redis
                    import json

                    redis = _get_redis()
                    if redis:
                        info = {"status": status, "persen": pct, "pesan": pesan or ""}
                        if self._operation_token is not None:
                            info["operation_token"] = self._operation_token
                        redis.setex(f"doc_embed_progress:{document_id}", 3600, json.dumps(info))
                except Exception as e:
                    logger.warning("Gagal menyimpan progress embed ke Redis untuk dokumen %d: %s", document_id, e)
                conn.execute(sql, {"id": document_id, "status": status, "pesan": pesan})
        except DocumentOperationCancelled:
            raise
        except Exception as e:
            logger.warning("Gagal mencatat status embed dokumen %d: %s", document_id, e)

    def keadaan(self, document_id: int) -> dict | None:
        """Ringkasan untuk endpoint status. None bila jobnya belum pernah ada."""
        sql = text(
            "SELECT j.document_id AS job_document_id, j.status, j.jeda_diminta, "
            "j.halaman_total, j.halaman_selesai, j.pesan, "
            "d.processing_token, d.cancellation_requested "
            "FROM documents d LEFT JOIN ekstraksi_job j ON j.document_id = d.id "
            "WHERE d.id = :id"
        )
        with self._engine.connect() as conn:
            baris = conn.execute(sql, {"id": document_id}).mappings().fetchone()
        if baris is None or (baris["job_document_id"] is None and not baris["cancellation_requested"]):
            return None

        total = baris["halaman_total"] or 0
        selesai = baris["halaman_selesai"] or 0
        persen = round(selesai / total * 100) if total else 0

        result = {
            "document_id": document_id,
            "status": "gagal" if baris["cancellation_requested"] else baris["status"],
            "jeda_diminta": bool(baris["jeda_diminta"]),
            "halaman_total": total,
            "halaman_selesai": selesai,
            "persen": max(0, min(100, persen)),
            "pesan": CANCELLATION_MESSAGE if baris["cancellation_requested"] else baris["pesan"],
        }
        if baris["cancellation_requested"]:
            return result

        # Cek jika ada kemajuan embedding aktif di Redis
        try:
            from app.services.session_memory import _get_redis
            r = _get_redis()
            if r:
                import json
                raw = r.get(f"doc_embed_progress:{document_id}")
                if raw:
                    info = json.loads(raw)
                    # A resumed generation cannot inherit progress published by
                    # the cancelled generation, including legacy untagged keys.
                    if info.get("operation_token") == baris["processing_token"]:
                        result.update({
                            "status": info.get("status", baris["status"]),
                            "persen": max(0, min(100, int(info.get("persen", persen)))),
                            "pesan": info.get("pesan", baris["pesan"]),
                        })
        except Exception:
            pass

        return result

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

    def reset_ekstraksi(self, document_id: int, *, only_cancelled: bool = False) -> None:
        """Reset extraction; late DELETE callbacks may require a still-cancelled row."""
        sql_halaman = text("DELETE FROM ekstraksi_halaman WHERE document_id = :id")
        sql_job = text("DELETE FROM ekstraksi_job WHERE document_id = :id")
        with self._write(document_id) as conn:
            if only_cancelled:
                from app.services.document_operations import _document_row
                row = _document_row(conn, document_id, lock=True)
                # A start may have won the race after vector cleanup completed.
                # The old DELETE callback must leave that new extraction alone.
                if row is not None and not row["cancellation_requested"]:
                    return
            conn.execute(sql_halaman, {"id": document_id})
            conn.execute(sql_job, {"id": document_id})


