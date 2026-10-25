"""Prompt OCR bawaan, petunjuk formulir, dan penyisipan istilah kategori.

Isi prompt dipertahankan utuh. Petunjuk kepala formulir hanya ditambahkan
ketika kepala memang terlihat; petunjuk tabel dapat dibawa antar halaman.
"""

_PROMPT_OCR_DASAR = (
    "Anda adalah sistem OCR. Salin SELURUH teks yang terlihat pada gambar ini.\n\n"

    "ATURAN:\n"
    "- Salin apa adanya. JANGAN meringkas, menafsirkan, atau menambahkan apa pun "
    "yang tidak tertulis di gambar.\n"
    "- Pertahankan urutan baca dokumen: atas ke bawah, kiri ke kanan.\n"
    "- Pertahankan penanda daftar PERSIS seperti tertulis (`1.`, `a.`, `aa.`, "
    "`iii.`). Jangan menomori ulang, jangan menyeragamkan.\n"
    "- Tulis isi tabel sebagai teks biasa atau daftar. JANGAN memakai tabel "
    "Markdown (tanda |).\n"
    "- Bila sebuah sel kosong, biarkan kosong. Jangan menebak isinya.\n"
    "- HANYA keluarkan teks hasil ekstraksi, tanpa penjelasan atau komentar.\n"
)


_PETUNJUK_TABEL_SOP = (
    "\nHALAMAN INI BERBENTUK FORMULIR SOP PEMERINTAH. Ikuti tambahan berikut.\n\n"

    "BAGIAN TABEL PROSEDUR (Uraian Prosedur / Langkah-langkah):\n"
    "HANYA UNTUK TABEL YANG MEMILIKI KOLOM 'Uraian Prosedur', 'Pelaksana', dan 'Mutu Baku', gunakan format ini PERSIS untuk setiap langkah:\n"
    "- <Nomor>. <Uraian Prosedur>\n"
    "  - Pelaksana: <nama jabatan yang ada centang/simbol di kolomnya>\n"
    "  - Kelengkapan: <isi kolom Kelengkapan>\n"
    "  - Waktu: <isi kolom Waktu>\n"
    "  - Output: <isi kolom Output>\n\n"

    "ATURAN TAMBAHAN:\n"
    "- Pelaksana ditentukan dari POSISI simbol flowchart (kotak/belah ketupat). Lihat simbol berada di bawah kolom jabatan mana.\n"
    "- Waktu dan Output adalah DUA kolom BERBEDA. JANGAN digabung. (Contoh BENAR: Waktu: 30 menit / Output: Disposisi).\n"
    "- Bila halaman ini TIDAK memuat kepala formulir ('Nomor SOP', 'Nama SOP', "
    "'Disahkan Oleh'), JANGAN membuatnya. Halaman lanjutan memang tidak punya kepala; "
    "menuliskannya berarti mengarang.\n"
)


_PETUNJUK_KEPALA_SOP = (
    "\nBAGIAN KEPALA FORMULIR (Teks Biasa & Daftar):\n"
    "Bagian seperti 'Nomor SOP', 'Nama SOP', 'Tanggal Pembuatan', 'Tanggal Pengesahan', 'Disahkan Oleh', "
    "'Dasar Hukum', 'Kualifikasi Pelaksana', 'Keterkaitan', 'Peralatan/Perlengkapan', "
    "dan 'Peringatan' BUKAN TABEL PROSEDUR. Tulis bagian ini SEBAGAI TEKS BIASA ATAU DAFTAR (LIST) NORMAL. "
    "DILARANG KERAS menambahkan atribut 'Pelaksana', 'Kelengkapan', 'Waktu', atau 'Output' pada bagian ini!\n\n"

    "WAJIB: bila halaman memuat 'Nomor SOP', maka baris 'Nama SOP' PASTI ada di kepala tabel yang sama — "
    "salin keduanya. JANGAN melewatkan 'Nama SOP'. Baris itu adalah judul prosedurnya dan tanpanya "
    "halaman ini tidak bisa dikenali.\n\n"

    # Sel 'Disahkan Oleh' berisi EMPAT baris bertumpuk, bukan satu nilai. Model
    # yang menulis kepala sebagai daftar 'Field: nilai' mengambil baris pertama
    # saja lalu pindah ke field berikutnya, dan nama pejabat beserta NIP-nya —
    # yang menempati dua pertiga bawah sel yang sama — hilang tanpa jejak.
    # Terukur: dari empat kali ekstraksi halaman berkepala, hanya SATU yang
    # menyalinnya, dan itu satu-satunya yang tidak memakai bentuk 'Field: nilai'.
    "WAJIB: sel 'Disahkan Oleh' memuat BEBERAPA BARIS bertumpuk — nama jabatan, "
    "lalu NAMA PEJABAT, lalu PANGKAT, lalu 'NIP.' beserta nomornya. Salin SEMUA "
    "barisnya, masing-masing pada baris sendiri. JANGAN berhenti setelah baris "
    "jabatan. Nama pejabat dan baris NIP sering tertindih stempel atau coretan "
    "tanda tangan — tetap salin, jangan dilewati.\n\n"

    "Tulis tiap bagian kepala sebagai baris terpisah, JANGAN memampatkan satu sel "
    "berisi banyak baris menjadi satu baris tunggal.\n"
)


_POLA_KATA_KUNCI = ("{kata_kunci}", "{job_titles}")


def _sisipkan_kata_kunci(prompt: str, kata_kunci: str) -> str:
    """
    Masukkan daftar kata kunci ke dalam prompt.

    Dua jalur, dan yang kedua yang membuatnya tidak bisa gagal diam-diam:
    ditulis sebagai penanda -> disisipkan PERSIS di posisi itu, sehingga admin
    mengendalikan letaknya; tidak ditulis (atau salah ketik) -> ditempelkan di
    akhir sebagai blok. Daftar yang sudah diisi admin tidak pernah hilang hanya
    karena penandanya keliru.
    """
    if not kata_kunci:
        return prompt

    for pola in _POLA_KATA_KUNCI:
        if pola in prompt:
            return prompt.replace(pola, kata_kunci)

    # Daftar telanjang tidak cukup: diuji pada halaman 8 SOP FULL, model tetap
    # menulis "Renatra" walau "Renstra" ada di daftar. Model perlu diberi tahu
    # apa yang harus DILAKUKAN dengan daftar itu, bukan sekadar disodori.
    # Kalimatnya juga membatasi diri — "hanya bila memang mirip" — supaya model
    # tidak memaksakan istilah dari daftar ke kata yang sebenarnya berbeda.
    return prompt + (
        "\n[ISTILAH & JABATAN RESMI]\n"
        "Dokumen ini memakai istilah berikut. Bila sebuah kata terbaca MIRIP "
        "salah satunya, tulis persis seperti daftar ini. Bila tidak mirip, "
        "salin apa adanya — jangan memaksakan istilah dari daftar.\n"
        f"{kata_kunci}\n"
    )


