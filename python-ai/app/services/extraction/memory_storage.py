"""Penyimpanan lokal untuk CLI satu proses; tidak berbagi flag dengan worker."""

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


