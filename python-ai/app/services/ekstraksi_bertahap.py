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

# Ekspor kompatibilitas untuk router, task, dan skrip yang memakai path lama.
from app.services.extraction.contracts import (
    STATUS_ANTRE,
    STATUS_BERJALAN,
    STATUS_JEDA,
    STATUS_MENUNGGU_KOREKSI,
    STATUS_SELESAI,
    STATUS_GAGAL,
    SEMUA_STATUS,
    Penyimpanan,
    Kemajuan,
)
from app.services.extraction.workflow import (
    _FLUSH_CACHE_INTERVAL,
    flush_ollama_cache,
    ekstrak_bertahap,
)
from app.services.extraction.memory_storage import (
    PenyimpananMemori,
)
from app.services.extraction.mysql_storage import (
    PenyimpananMySQL,
)
