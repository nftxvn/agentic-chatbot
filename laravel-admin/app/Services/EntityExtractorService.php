<?php

namespace App\Services;

use App\Models\ChatTicket;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Redis;
use Illuminate\Support\Str;

class EntityExtractorService
{
    /**
     * Kata-kata umum bahasa Indonesia yang dilarang menjadi 'Nama' (False Positives).
     */
    protected static array $nameStopwords = [
        'mau', 'ingin', 'butuh', 'perlu', 'ada', 'hendak', 'belum', 'tidak', 'tak', 'bukan',
        'sedang', 'baru', 'sudah', 'telah', 'minta', 'mohon', 'bertanya', 'tanya', 'bingung',
        'rasa', 'kira', 'cuma', 'hanya', 'kan', 'ini', 'itu', 'warga', 'masyarakat', 'umum',
        'seorang', 'seseorang', 'admin', 'petugas', 'operator', 'cs', 'pihak', 'siapa',
        'bantuan', 'cara', 'cepat', 'mudah', 'baik', 'bisa', 'boleh', 'dapat', 'tolong',
        'halo', 'hai', 'selamat', 'pagi', 'siang', 'sore', 'malam', 'assalamualaikum',
        'waalaikumsalam', 'terima', 'kasih', 'makasih', 'bapak', 'ibu', 'pak', 'bu', 'mas', 'mbak',
        'hormat', 'info', 'informasi', 'kendala', 'masalah', 'keluhan', 'keperluan', 'perihal',
        'dari', 'staf', 'pegawai', 'kantor', 'instansi', 'opd', 'dinas', 'badan', 'bagian', 'bidang',
        'kementerian', 'di', 'ke', 'pada', 'untuk', 'atas', 'nama', 'dengan', 'saya', 'kami', 'adalah',
    ];

    /**
     * Daftar singkatan / alias instansi umum Pemko Banda Aceh, Kementerian & Lembaga.
     */
    protected static array $agencyAliases = [
        'kemenkes' => 'Kementerian Kesehatan',
        'kemendikbud' => 'Kementerian Pendidikan dan Kebudayaan',
        'kemenag' => 'Kementerian Agama',
        'kemendagri' => 'Kementerian Dalam Negeri',
        'kemenkeu' => 'Kementerian Keuangan',
        'kemenkumham' => 'Kemenkumham',
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

        // 1. Ekstraksi format terstruktur Key-Value (e.g. Nama: Budi, Instansi: Dinkes, Instansi/OPD: Kemenkes)
        if (preg_match('/(?:nama|name)\s*[:=]\s*([^,\/\n\|\.]+)/i', $cleanText, $m)) {
            $cand = self::cleanName($m[1]);
            if ($cand) {
                $name = $cand;
            }
        }
        if (preg_match('/(?:instansi(?:\s*\/\s*opd)?|opd|unit\s+kerja|kantor|asal)\s*[:=]\s*([^,\/\n\|\.]+)/i', $cleanText, $m)) {
            $cand = self::cleanAgency($m[1]);
            if ($cand) {
                $agency = $cand;
            }
        }
        if (preg_match('/(?:kendala|masalah|keluhan|keperluan|perihal|kebutuhan)\s*[:=]\s*(.+)/is', $cleanText, $m)) {
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
                '/(?:nama\s*(?:saya|ku)?|namaku|atas\s+nama|panggil\s+saja)\s*(?:adalah|:|=)?\s*([A-Za-z\s\'\.]{2,35}?)(?=\s+(?:dari|staf|pegawai|instansi|kantor|opd|kendala|masalah|keperluan|ingin|mau|tolong|\.|\,|\n|$))/i',
                '/(?:perkenalkan\s+saya|saya|dengan|aku)\s+([A-Za-z\s\'\.]{2,30}?)(?=\s+(?:dari|staf|pegawai|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|\.|\,|\n|$))/i',
                '/\bnama\s+([A-Za-z\s\'\.]{2,30}?)(?=\s+(?:dari|staf|pegawai|instansi|kantor|opd|dinas|badan|bagian|kementerian|kecamatan|puskesmas|uin|usk|universitas|\.|\,|\n|$))/i',
                '/^([A-Za-z\s\'\.]{2,30}?)\s+(?:dari|instansi|asal|kantor|staf|pegawai)\s+/i',
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
                '/(?:dari|staf\s+(?:di|pada|ke)?|pegawai\s+(?:di|pada|ke)?|kantor|bagian|bidang|opd|instansi|asal)\s*[:=]?\s*([A-Za-z0-9\s\'\.\-_]{2,50}?)(?=\s+(?:mau|ingin|butuh|perlu|tolong|mohon|kendala|masalah|keluhan|keperluan|\.|\,|\n|$))/i',
                '/\b(dinas\s+[a-z0-9\s\.\-_]+|badan\s+[a-z0-9\s\.\-_]+|kementerian\s+[a-z0-9\s\.\-_]+|universitas\s+[a-z0-9\s\.\-_]+|kampus\s+[a-z0-9\s\.\-_]+|inspektorat(?:\s+[a-z0-9\s\.\-_]+)?|setda(?:ko)?(?:\s+[a-z0-9\s\.\-_]+)?|sekretariat\s+daerah(?:\s+[a-z0-9\s\.\-_]+)?|satpol\s*pp(?:\s*&\s*wh)?|kecamatan\s+[a-z0-9\s\.\-_]+|camat\s+[a-z0-9\s\.\-_]+|puskesmas\s+[a-z0-9\s\.\-_]+|rsud\s+[a-z0-9\s\.\-_]+|bagian\s+[a-z0-9\s\.\-_]+|bidang\s+[a-z0-9\s\.\-_]+)\b/i',
                '/\b(kemenkes|kemendikbud|kemenag|kemendagri|kemenkeu|kemenkumham|bappeda|bkpsdm|bpkk|bpbd|diskominfo[a-z]*|dinkes|diskes|disdikbud|disdik|dishub|dinsos|pupr|dlhk3?|dpmptsp|uin(?:\s+ar[\s\-]raniry)?|usk|unsyiah|unida|ummuha|poltekkes)(?:\s+[a-z0-9\s\.\-_]+)?\b/i',
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

    /**
     * Membaca riwayat percakapan dari Redis DB 2 (chatbot:session:{$sessionId})
     * dan mengekstrak entitas Nama, Instansi, dan Ringkasan Masalah dari multi-turn chat sebelumnya.
     */
    public static function extractFromSessionHistory(string $sessionId, ?string $fallbackName = null): array
    {
        $extractedName = null;
        $extractedAgency = null;
        $extractedIssue = null;
        $extractedContact = null;
        $firstInquiry = null;

        if (empty($sessionId)) {
            return [
                'name' => self::cleanName($fallbackName),
                'agency' => null,
                'issue_summary' => null,
                'contact' => null,
            ];
        }

        try {
            $redis = Redis::connection();
            $redis->select(2);
            $raw = $redis->get("chatbot:session:{$sessionId}");

            if ($raw) {
                $sessionData = json_decode($raw, true);
                if (is_array($sessionData) && !empty($sessionData['messages'])) {
                    $messages = $sessionData['messages'];

                    // Telusuri riwayat pesan dari awal ke akhir
                    foreach ($messages as $msg) {
                        if (($msg['role'] ?? '') === 'user') {
                            $userContent = trim($msg['content'] ?? '');
                            if (empty($userContent)) {
                                continue;
                            }

                            // Simpan pertanyaan substantif pertama yang bukan sekadar sapaan/hubungi admin
                            if (!$firstInquiry && !self::isPureGreetingOrHandoff($userContent)) {
                                $firstInquiry = $userContent;
                            }

                            // Ekstrak entitas dari pesan user ini
                            $res = self::extractFromText($userContent, $fallbackName);
                            if (!$extractedName && !empty($res['name'])) {
                                $extractedName = $res['name'];
                            }
                            if (!$extractedAgency && !empty($res['agency'])) {
                                $extractedAgency = $res['agency'];
                            }
                            if (!$extractedIssue && !empty($res['issue_summary'])) {
                                $extractedIssue = $res['issue_summary'];
                            }
                            if (!$extractedContact && !empty($res['contact'])) {
                                $extractedContact = $res['contact'];
                            }
                        }
                    }
                }
            }
        } catch (\Exception $e) {
            Log::warning("EntityExtractorService: Gagal membaca Redis session {$sessionId}: " . $e->getMessage());
        }

        // Jika issue belum terisi tapi ada riwayat pertanyaan substantif sebelumnya
        if (!$extractedIssue && $firstInquiry) {
            $extractedIssue = "Pertanyaan: " . Str::limit($firstInquiry, 140);
        }

        // Fallback nama ke sender profile jika belum ada
        if (!$extractedName && !empty($fallbackName) && !in_array(strtolower(trim($fallbackName)), ['user', 'warga', 'anonim', 'defaultuser'])) {
            $extractedName = self::cleanName($fallbackName);
        }

        return [
            'name' => $extractedName,
            'agency' => $extractedAgency,
            'issue_summary' => $extractedIssue,
            'contact' => $extractedContact,
        ];
    }

    /**
     * Memperkaya (auto-enrich) tiket yang sedang berjalan secara dinamis
     * jika warga memberikan informasi identitas/kendala baru di tengah percakapan.
     */
    public static function enrichTicket(ChatTicket $ticket, string $incomingText, ?string $senderName = null): bool
    {
        $entities = self::extractFromText($incomingText, $senderName);
        $updated = false;

        // 1. Perbarui Nama jika saat ini masih kosong / default ('Warga', 'Warga / Anonim', dsb.)
        $currentName = trim($ticket->citizen_name ?? '');
        $isGenericName = empty($currentName) || in_array(strtolower($currentName), ['warga', 'warga / anonim', 'warga telegram', 'warga whatsapp', 'user', 'anonim', 'defaultuser']);

        if ($isGenericName && !empty($entities['name'])) {
            $ticket->citizen_name = $entities['name'];
            $updated = true;

            // Retroaktif perbarui sender_name pesan warga sebelumnya yang masih 'Warga'
            try {
                $ticket->messages()
                    ->where('sender_type', 'citizen')
                    ->whereIn('sender_name', ['Warga', 'Warga / Anonim', 'Warga Telegram', 'Warga WhatsApp', 'User'])
                    ->update(['sender_name' => $entities['name']]);
            } catch (\Exception $e) {
                // Ignore
            }
        }

        // 2. Perbarui Instansi jika belum ada
        if (empty($ticket->citizen_agency) && !empty($entities['agency'])) {
            $ticket->citizen_agency = $entities['agency'];
            $updated = true;
        }

        // 3. Perbarui Ringkasan Masalah jika saat ini hanya generic "hubungi admin" atau kosong atau sapaan
        $currentIssue = strtolower(trim($ticket->issue_summary ?? ''));
        $isGenericIssue = empty($currentIssue) 
            || str_contains($currentIssue, 'hubungi admin')
            || str_contains($currentIssue, 'hubungkan')
            || str_contains($currentIssue, 'permintaan bantuan langsung')
            || str_contains($currentIssue, 'assalamualaikum')
            || str_contains($currentIssue, 'halo')
            || str_contains($currentIssue, 'selamat')
            || str_starts_with($currentIssue, 'pertanyaan:');

        if ($isGenericIssue && !empty($entities['issue_summary'])) {
            $ticket->issue_summary = Str::limit($entities['issue_summary'], 250);
            $updated = true;
        } elseif ($isGenericIssue && !empty($entities['agency']) && !empty($ticket->citizen_name)) {
            $ticket->issue_summary = "Bantuan koordinasi untuk {$ticket->citizen_name} ({$ticket->citizen_agency})";
            $updated = true;
        }

        if ($updated) {
            $ticket->save();
            Log::info("ChatTicket #{$ticket->id} berhasil diperkaya dengan entitas baru:", [
                'citizen_name' => $ticket->citizen_name,
                'citizen_agency' => $ticket->citizen_agency,
                'issue_summary' => $ticket->issue_summary,
            ]);
        }

        return $updated;
    }

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
            $lower = preg_replace('/^(?:dari|staf\s+di|staf|pegawai\s+di|pegawai|kantor|opd|instansi|asal)\s+/i', '', $lower);
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
