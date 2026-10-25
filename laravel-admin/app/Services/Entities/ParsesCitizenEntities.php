<?php

namespace App\Services\Entities;

/**
 * Parsing entitas dari satu pesan dengan pola dan prioritas yang sama.
 *
 * Trait dimuat pada EntityExtractorService untuk mempertahankan binding self::
 * serta properti/helper protected tanpa menyalin state atau algoritme.
 *
 * @mixin \App\Services\EntityExtractorService
 */
trait ParsesCitizenEntities
{
    /**
     * Ekstraksi entitas (Nama, Instansi, Kendala, Kontak) dari sebaris teks / pesan.
     */
    public static function extractFromText(string $text, ?string $fallbackName = null): array
    {
        $text = trim($text);
        $name = null;
        $agency = null;
        $issue = null;
        $contact = null;

        // Bersihkan simbol markdown bullets dan bolding agar parsing key-value tahan terhadap copy-paste template
        $cleanText = preg_replace('/[*_•\-]+/', ' ', $text);

        // Pola lookahead pembatas agar tidak merebut kunci berikutnya dalam 1 baris
        $nextKeyPattern = '(?=\s+(?:nama|instansi|opd|unit\s+kerja|kantor|asal|kendala|masalah|keluhan|keperluan|perihal|kebutuhan|hp|wa|telepon|kontak|telp|no)\s*[:=]|$|\n|\,|\/|\|)';

        // 1. Ekstraksi format terstruktur Key-Value (e.g. Nama: Budi, Nama saya: Budi, Instansi: Dinkes, Instansi/OPD: Kemenkes)
        if (preg_match('/(?:nama(?:\s*(?:saya|ku))?|name)\s*[:=]\s*([^,\/\n\|\.]+?)' . $nextKeyPattern . '/i', $cleanText, $m)) {
            $cand = self::cleanName($m[1]);
            if ($cand) {
                $name = $cand;
            }
        }
        if (preg_match('/(?:instansi(?:\s*\/\s*opd)?|opd|unit\s+kerja|kantor|asal)\s*[:=]\s*([^,\/\n\|\.]+?)' . $nextKeyPattern . '/i', $cleanText, $m)) {
            $cand = self::cleanAgency($m[1]);
            if ($cand) {
                $agency = $cand;
            }
        }
        if (preg_match('/(?:kendala|masalah|keluhan|keperluan|perihal|kebutuhan)\s*[:=]\s*(.+?)' . $nextKeyPattern . '/is', $cleanText, $m)) {
            $rawIssue = trim($m[1]);
            $rawIssue = preg_replace('/^(?:saya|kami|adalah|yaitu)?\s*[:=]?\s*/i', '', $rawIssue);
            $issue = trim($rawIssue);
        }
        if (preg_match('/(?:hp|wa|telepon|kontak|telp|no)\s*[:=]\s*([0-9\+\-\s]{8,20})/i', $cleanText, $m)) {
            $contact = trim($m[1]);
        }

        // 2. Ekstraksi Nama Bahasa Indonesia berbasis Pola Percakapan Alami
        if (!$name) {
            $namePatterns = [
                '/(?:nama\s*(?:saya|ku)?|namaku|atas\s+nama|panggil\s+saja)\s*(?:adalah|:|=)?\s*([A-Za-z\s\'\.]{2,35}?)(?=\s+(?:dari|staf|pegawai|mahasiswa|mahasiswi|dosen|guru|honorer|asn|pns|pppk|siswa|siswi|pelajar|alumni|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|kendala|masalah|keperluan|ingin|mau|tolong|dan|serta|\.|\,|\n|$))/i',
                '/(?:perkenalkan\s+(?:nama\s+)?saya|perkenalkan)\s+([A-Za-z\s\'\.]{2,30}?)(?=\s+(?:dari|staf|pegawai|mahasiswa|mahasiswi|dosen|guru|honorer|asn|pns|pppk|siswa|siswi|pelajar|alumni|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|kendala|masalah|keperluan|ingin|mau|tolong|dan|serta|\.|\,|\n|$))/i',
                '/(?:saya|dengan|aku)\s+([A-Za-z\s\'\.]{2,30}?)\s+(?:dari|staf\s+(?:di|pada|ke)?|pegawai\s+(?:di|pada|ke)?|mahasiswa\s+(?:di|pada|ke)?|mahasiswi\s+(?:di|pada|ke)?|dosen\s+(?:di|pada|ke)?|guru\s+(?:di|pada|ke)?|kantor|opd|instansi|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas)\b/i',
                '/^([A-Za-z\s\'\.]{2,30}?)\s+(?:dari|instansi|asal|kantor|staf|pegawai|mahasiswa|mahasiswi|dosen|guru)\s+/i',
            ];

            foreach ($namePatterns as $pattern) {
                if (preg_match($pattern, $text, $m)) {
                    $cleaned = self::cleanName($m[1]);
                    if ($cleaned) {
                        $name = $cleaned;
                        break;
                    }
                }
            }
        }

        // 3. Ekstraksi Instansi / OPD / Kementerian / Kampus berbasis Pola Alami & Keyword
        if (!$agency) {
            $agencyPatterns = [
                '/(?:dari|staf\s+(?:di|pada|ke)?|pegawai\s+(?:di|pada|ke)?|mahasiswa\s+(?:di|pada|ke)?|mahasiswi\s+(?:di|pada|ke)?|dosen\s+(?:di|pada|ke)?|guru\s+(?:di|pada|ke)?|alumni\s+(?:dari)?|kantor|bagian|bidang|opd|instansi|asal)\s*[:=]?\s*([A-Za-z0-9\s\'\.\-_]{2,50}?)(?=\s+(?:mau|ingin|butuh|perlu|tolong|mohon|kendala|masalah|keluhan|keperluan|\.|\,|\n|$))/i',
                '/\b(dinas\s+[a-z0-9\s\.\-_]+|badan\s+[a-z0-9\s\.\-_]+|kementerian\s+[a-z0-9\s\.\-_]+|universitas\s+[a-z0-9\s\.\-_]+|kampus\s+[a-z0-9\s\.\-_]+|inspektorat(?:\s+[a-z0-9\s\.\-_]+)?|setda(?:ko)?(?:\s+[a-z0-9\s\.\-_]+)?|sekretariat\s+daerah(?:\s+[a-z0-9\s\.\-_]+)?|satpol\s*pp(?:\s*&\s*wh)?|kecamatan\s+[a-z0-9\s\.\-_]+|camat\s+[a-z0-9\s\.\-_]+|puskesmas\s+[a-z0-9\s\.\-_]+|rsud\s+[a-z0-9\s\.\-_]+|bagian\s+[a-z0-9\s\.\-_]+|bidang\s+[a-z0-9\s\.\-_]+)\b/i',
                '/\b(kemenkes|kemkes|kemendikbud|kemedikbud|kemdikbud|kemendikbudristek|kemenag|kemendagri|kemendag|kemenkeu|kemenkumham|kemenko|kemenhub|kemenpan|kemenpanrb|kemkominfo|komdigi|bappeda|bkpsdm|bpkk|bpbd|diskominfo[a-z]*|dinkes|diskes|disdikbud|disdik|dishub|dinsos|pupr|dlhk3?|dpmptsp|uin(?:\s+ar[\s\-]raniry)?|usk|unsyiah|unida|ummuha|poltekkes)(?:\s+[a-z0-9\s\.\-_]+)?\b/i',
            ];

            foreach ($agencyPatterns as $pattern) {
                if (preg_match($pattern, $text, $m)) {
                    $cleaned = self::cleanAgency($m[1]);
                    if ($cleaned) {
                        $agency = $cleaned;
                        break;
                    }
                }
            }
        }

        // 4. Ekstraksi Kendala / Masalah Alami jika belum terisi
        if (!$issue) {
            if (preg_match('/(?:kendala|masalah|keluhan|keperluan|perihal)\s*(?:saya|kami)?\s*[:=]?\s*(.+)/i', $text, $m)) {
                $rawIssue = trim($m[1]);
                $rawIssue = preg_replace('/^(?:saya|kami|adalah|yaitu)?\s*[:=]?\s*/i', '', $rawIssue);
                $issue = trim($rawIssue);
            } elseif (preg_match('/(?:ingin|mau|butuh|perlu|mohon|tolong)\s+(?:bantuan\s+(?:untuk\s+)?)?(.+)/i', $text, $m)) {
                $candidate = trim($m[1]);
                if (!preg_match('/^(?:hubungi\s+admin|hubungkan\s+ke\s+admin|bicara\s+dengan\s+manusia|tanya)$/i', $candidate)) {
                    $issue = $candidate;
                }
            }
        }

        // 5. Fallback Nama jika tidak terdeteksi dari teks tapi ada profil pengirim (e.g. Telegram / WA)
        if (!$name && !empty($fallbackName) && !in_array(strtolower(trim($fallbackName)), ['user', 'warga', 'anonim', 'null', 'defaultuser'])) {
            $name = self::cleanName($fallbackName);
        }

        return [
            'name' => $name,
            'agency' => $agency,
            'issue_summary' => $issue,
            'contact' => $contact,
        ];
    }
}
