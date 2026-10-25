<?php

namespace App\Services\Entities;

/**
 * Leksikon dan normalisasi nama/instansi serta penjaga sapaan.
 *
 * Trait dimuat pada EntityExtractorService untuk mempertahankan binding self::
 * serta properti/helper protected tanpa menyalin state atau algoritme.
 *
 * @mixin \App\Services\EntityExtractorService
 */
trait NormalizesCitizenEntities
{
    /**
     * Kata-kata umum bahasa Indonesia yang dilarang menjadi 'Nama' (False Positives).
     */
    protected static array $nameStopwords = [
        'mau', 'ingin', 'butuh', 'perlu', 'ada', 'hendak', 'belum', 'tidak', 'tak', 'bukan',
        'sedang', 'baru', 'sudah', 'telah', 'minta', 'mohon', 'bertanya', 'tanya', 'bingung',
        'rasa', 'kira', 'cuma', 'hanya', 'kan', 'ini', 'itu', 'warga', 'masyarakat', 'umum',
        'seorang', 'seseorang', 'orang', 'admin', 'petugas', 'operator', 'cs', 'helpdesk', 'pihak', 'siapa',
        'manusia', 'staf', 'staff', 'tim', 'bantuan', 'cara', 'cepat', 'mudah', 'baik', 'bisa',
        'boleh', 'dapat', 'tolong', 'dong', 'halo', 'hai', 'selamat', 'pagi', 'siang', 'sore',
        'malam', 'assalamualaikum', 'waalaikumsalam', 'terima', 'kasih', 'makasih', 'bapak',
        'ibu', 'pak', 'bu', 'mas', 'mbak', 'hormat', 'info', 'informasi', 'kendala', 'masalah',
        'keluhan', 'keperluan', 'perihal', 'kebutuhan', 'dari', 'kantor', 'instansi', 'opd',
        'dinas', 'badan', 'bagian', 'bidang', 'kementerian', 'lembaga', 'kecamatan', 'puskesmas',
        'di', 'ke', 'pada', 'untuk', 'atas', 'nama', 'dengan', 'sama', 'saya', 'kami', 'kita',
        'adalah', 'yaitu', 'dan', 'serta', 'yg', 'yang', 'juga', 'atau', 'pun', 'karena', 'sebab',
        'bicara', 'berbicara', 'ngobrol', 'ngomong', 'diskusi', 'konsultasi', 'konsul', 'chat',
        'chatting', 'hubung', 'hubungi', 'menghubungi', 'dihubungi', 'sambung', 'sambungkan',
        'hubungkan', 'alih', 'alihkan', 'kontak', 'mengontak', 'pesan', 'kirim', 'bertemu',
        'ketemu', 'panggil', 'langsung',
        'mahasiswa', 'mahasiswi', 'dosen', 'guru', 'honorer', 'asn', 'pns', 'pppk', 'siswa',
        'siswi', 'pelajar', 'alumni', 'rekan', 'anggota', 'kepala', 'ketua', 'sekretaris',
        'bendahara', 'kabid', 'kasi', 'kadis', 'direktur', 'dekan', 'rektor',
    ];

    /**
     * Daftar singkatan / alias instansi umum Pemko Banda Aceh, Kementerian & Lembaga.
     */
    protected static array $agencyAliases = [
        'kemenkes' => 'Kementerian Kesehatan',
        'kemkes' => 'Kementerian Kesehatan',
        'kemendikbud' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemedikbud' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemdikbud' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemendikbudristek' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemendiknas' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemenag' => 'Kementerian Agama',
        'kemag' => 'Kementerian Agama',
        'kemendagri' => 'Kementerian Dalam Negeri',
        'kemendag' => 'Kementerian Perdagangan',
        'kemenkeu' => 'Kementerian Keuangan',
        'kemenkumham' => 'Kemenkumham',
        'kemenko' => 'Kementerian Koordinator',
        'kemenhub' => 'Kementerian Perhubungan',
        'kemenpan' => 'KemenPAN-RB',
        'kemenpanrb' => 'KemenPAN-RB',
        'kemkominfo' => 'Kementerian Komunikasi dan Digital',
        'komdigi' => 'Kementerian Komunikasi dan Digital',
        'diskominfo' => 'Diskominfotik',
        'diskominfotik' => 'Diskominfotik',
        'kominfo' => 'Diskominfotik',
        'bappeda' => 'Bappeda',
        'bkpsdm' => 'BKPSDM',
        'bpkk' => 'BPKK',
        'bpbd' => 'BPBD',
        'dinkes' => 'Dinas Kesehatan',
        'diskes' => 'Dinas Kesehatan',
        'disdik' => 'Dinas Pendidikan dan Kebudayaan',
        'disdikbud' => 'Dinas Pendidikan dan Kebudayaan',
        'disdukcapil' => 'Disdukcapil',
        'dukcapil' => 'Disdukcapil',
        'dishub' => 'Dinas Perhubungan',
        'dinsos' => 'Dinas Sosial',
        'pupr' => 'Dinas PUPR',
        'dlhk' => 'DLHK3',
        'dlhk3' => 'DLHK3',
        'dpmptsp' => 'DPMPTSP',
        'inspektorat' => 'Inspektorat',
        'setda' => 'Setda Kota Banda Aceh',
        'setdako' => 'Setdako Banda Aceh',
        'satpol' => 'Satpol PP & WH',
        'satpolpp' => 'Satpol PP & WH',
        'satpol pp' => 'Satpol PP & WH',
        'uin' => 'UIN Ar-Raniry',
        'uin ar raniry' => 'UIN Ar-Raniry',
        'uin ar-raniry' => 'UIN Ar-Raniry',
        'ar raniry' => 'UIN Ar-Raniry',
        'ar-raniry' => 'UIN Ar-Raniry',
        'usk' => 'Universitas Syiah Kuala',
        'unsyiah' => 'Universitas Syiah Kuala',
        'unida' => 'Universitas Iskandar Muda',
        'ummuha' => 'Universitas Muhammadiyah Aceh',
        'poltekkes' => 'Poltekkes Kemenkes Aceh',
        'bbpmp' => 'BBPMP Aceh',
        'lan' => 'Puslatbang KHAN LAN RI',
    ];

    /**
     * Validasi dan pembersihan teks nama warga.
     */
    public static function cleanName(?string $raw): ?string
    {
        if (empty($raw)) {
            return null;
        }

        // Bersihkan tanda baca tepi
        $trimmed = trim($raw, " \t\n\r\0\x0B.,:;!?-/|");
        $cleaned = trim(preg_replace('/[^A-Za-z\s\'\.]/', '', $trimmed));
        $rawWords = preg_split('/\s+/', $cleaned);

        if (empty($rawWords) || empty($rawWords[0])) {
            return null;
        }

        // Filter kata-kata depan dan belakang yang termasuk stopwords/prepositions
        $validWords = [];
        foreach ($rawWords as $w) {
            $wLower = strtolower($w);
            if (in_array($wLower, self::$nameStopwords)) {
                if (!empty($validWords)) {
                    break;
                }
                continue;
            }
            $validWords[] = $w;
        }

        if (empty($validWords)) {
            return null;
        }

        // Batasi panjang nama yang wajar (1 - 4 kata)
        if (count($validWords) > 4) {
            $validWords = array_slice($validWords, 0, 4);
        }

        $finalName = ucwords(strtolower(implode(' ', $validWords)));
        return strlen($finalName) >= 2 ? $finalName : null;
    }

    /**
     * Validasi dan standardisasi nama instansi / dinas.
     */
    public static function cleanAgency(?string $raw): ?string
    {
        if (empty($raw)) {
            return null;
        }

        // Bersihkan tanda baca tepi
        $rawTrim = trim($raw, " \t\n\r\0\x0B.,:;!?-/|");
        $lower = strtolower($rawTrim);

        // Bersihkan prefix umum jika tersisa, KECUALI jika diikuti nama dinas/badan/bagian/kementerian
        if (!preg_match('/^(?:dinas|badan|bagian|bidang|kementerian|kecamatan|puskesmas|rsud|setda|inspektorat)\b/i', $lower)) {
            $lower = preg_replace('/^(?:dari|staf\s+di|staf|pegawai\s+di|pegawai|mahasiswa\s+di|mahasiswa|mahasiswi\s+di|mahasiswi|dosen\s+di|dosen|guru|alumni|kantor|opd|instansi|asal)\s+/i', '', $lower);
        }
        $lower = trim($lower, " \t\n\r\0\x0B.,:;!?-/|");

        // Cek alias langsung (e.g. "kemenkes" -> "Kementerian Kesehatan", "uin" -> "UIN Ar-Raniry")
        $aliases = self::$agencyAliases;
        uksort($aliases, fn($a, $b) => strlen($b) <=> strlen($a));

        foreach ($aliases as $alias => $canonical) {
            if ($lower === $alias || str_starts_with($lower, $alias . ' ') || str_starts_with($lower, $alias . ',')) {
                $suffix = trim(substr($lower, strlen($alias)), " ,-");
                if (empty($suffix) || str_contains(strtolower($canonical), strtolower($suffix))) {
                    return $canonical;
                }
                return trim($canonical . ' ' . ucwords($suffix));
            }
        }

        // Standardisasi kapitalisasi kata-kata resmi
        $cleaned = ucwords(strtolower($lower));
        $cleaned = preg_replace('/\bOpd\b/i', 'OPD', $cleaned);
        $cleaned = preg_replace('/\bSppd\b/i', 'SPPD', $cleaned);
        $cleaned = preg_replace('/\bSop\b/i', 'SOP', $cleaned);
        $cleaned = preg_replace('/\bBkpsdm\b/i', 'BKPSDM', $cleaned);
        $cleaned = preg_replace('/\bBappeda\b/i', 'Bappeda', $cleaned);
        $cleaned = preg_replace('/\bBpkk\b/i', 'BPKK', $cleaned);
        $cleaned = preg_replace('/\bBpbd\b/i', 'BPBD', $cleaned);
        $cleaned = preg_replace('/\bRsud\b/i', 'RSUD', $cleaned);
        $cleaned = preg_replace('/\bUptd\b/i', 'UPTD', $cleaned);
        $cleaned = preg_replace('/\bDlhk3?\b/i', 'DLHK3', $cleaned);
        $cleaned = preg_replace('/\bDisdukcapil\b/i', 'Disdukcapil', $cleaned);
        $cleaned = preg_replace('/\bDpmptsp\b/i', 'DPMPTSP', $cleaned);

        return strlen($cleaned) >= 2 ? $cleaned : null;
    }

    /**
     * Deteksi apakah pesan hanya sekadar sapaan pembuka atau permintaan handover murni.
     */
    protected static function isPureGreetingOrHandoff(string $text): bool
    {
        $lower = strtolower(trim($text));
        $purePatterns = [
            '/^(?:halo|hai|selamat\s+(?:pagi|siang|sore|malam)|assalamualaikum|waalaikumsalam|ping|p|tes|test|hallo)$/i',
            '/^(?:hubungi\s+admin|hubungkan\s+(?:dengan\s+)?(?:admin|petugas)|tolong\s+hubungkan\s+saya\s+(?:dengan\s+)?admin|bicara\s+dengan\s+manusia)$/i',
        ];

        foreach ($purePatterns as $pattern) {
            if (preg_match($pattern, $lower)) {
                return true;
            }
        }

        return false;
    }
}
