"""Status ekstraksi, protokol penyimpanan, dan struktur laporan kemajuan."""

from dataclasses import dataclass, field
from typing import Protocol

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


