<?php

namespace App\Services;

use App\Models\AppSetting;
use App\Models\ChatbotDirectory;
use App\Models\ChatbotFastPath;
use Illuminate\Support\Facades\Log;

class GracefulDegradationService
{
    /**
     * Pola regex untuk sapaan umum (Indonesia & Aceh)
     */
    protected static string $greetingRegex = '/^(?:(?:halo|hai|hay|hei|hi|hello|assalamu[\'\s]?alaikum(?:\s+wr\s+wb|\s+warahmatullahi\s+wabarakatuh)?|ass|askum|saleuem(?:\s+teuka)?|saleum(?:\s+teuka)?|kru\s+seumangat|kiban\s+haba|haba\s+kiban|peue\s+haba|peu\s+haba|selamat\s+(?:pagi|siang|sore|malam)|pagi|siang|sore|malam|tes|test|ping|p|testing|terima\s+kasih|makasih|thanks|syukron|teurimong\s+gaseh)[\s,.-]*)+$/i';

    /**
     * Menghasilkan jawaban fallback yang ramah dan kontekstual ketika AI Service offline/down.
     *
     * @param string $query Pertanyaan pengguna
     * @return array{answer: string, is_fallback: bool, sources: array, source_type: string}
     */
    public static function resolveFallback(string $query): array
    {
        $q = trim($query);
        $qLower = strtolower($q);

        // 1. Sapaan Cepat (Greeting)
        if (preg_match(self::$greetingRegex, $qLower)) {
            $botName = AppSetting::getVal('chatbot_name', 'Layanan Informasi Diskominfotik');
            return [
                'answer' => "Assalamu'alaikum! Selamat datang di {$botName} Kota Banda Aceh. Ada yang dapat kami bantu terkait informasi dan layanan kedinasan?",
                'is_fallback' => false,
                'sources' => [],
                'source_type' => 'local_greeting',
            ];
        }

        // 2. Cari kecocokan di Database Fast-Paths Lokal (FAQ & Info Instansi)
        try {
            $fastPaths = ChatbotFastPath::where('is_active', true)
                ->orderBy('sort_order', 'asc')
                ->get();

            foreach ($fastPaths as $fp) {
                if (self::matchesKeywords($qLower, $fp->keywords, $fp->title)) {
                    return [
                        'answer' => $fp->response_text,
                        'is_fallback' => false,
                        'sources' => [
                            ['doc_name' => "Informasi Resmi: {$fp->title}", 'page' => null],
                        ],
                        'source_type' => 'local_fast_path',
                    ];
                }
            }
        } catch (\Exception $e) {
            Log::warning('GracefulDegradation: Gagal query chatbot_fast_paths: ' . $e->getMessage());
        }

        // 3. Cari kecocokan di Database Direktori Bidang Lokal
        try {
            $directories = ChatbotDirectory::where('is_active', true)
                ->orderBy('sort_order', 'asc')
                ->get();

            foreach ($directories as $dir) {
                if (self::matchesKeywords($qLower, $dir->keywords, $dir->nama_bidang)) {
                    $tugasText = '';
                    if (!empty($dir->daftar_tugas) && is_array($dir->daftar_tugas)) {
                        $tugasItems = array_map(fn($t) => "  • {$t}", $dir->daftar_tugas);
                        $tugasText = "\n\n*Fungsi & Tugas Utama:*\n" . implode("\n", $tugasItems);
                    }

                    $answer = "*{$dir->nama_bidang} — Diskominfotik Kota Banda Aceh*\n\n"
                        . "• *Lokasi / Ruangan:* {$dir->lokasi}\n"
                        . "• *Layanan Utama:* {$dir->layanan_utama}\n"
                        . "• *Jam Operasional:* {$dir->jam_operasional}\n"
                        . ($dir->email ? "• *Email Layanan:* {$dir->email}" : "")
                        . $tugasText;

                    return [
                        'answer' => trim($answer),
                        'is_fallback' => false,
                        'sources' => [
                            ['doc_name' => "Direktori Unit Kerja: {$dir->nama_bidang}", 'page' => null],
                        ],
                        'source_type' => 'local_directory',
                    ];
                }
            }
        } catch (\Exception $e) {
            Log::warning('GracefulDegradation: Gagal query chatbot_directories: ' . $e->getMessage());
        }

        // 4. Fallback Pemeliharaan Resmi yang Ramah & Solutif
        $emergencyAnswer = "Mohon maaf, layanan konsultasi otomatis kami saat ini sedang dalam peningkatan sistem berkala.\n\n"
            . "Untuk kebutuhan informasi resmi dan bantuan mendesak, silakan hubungi:\n"
            . "• *Call Center Darurat:* 112\n"
            . "• *Email Layanan:* diskominfotik@bandaacehkota.go.id\n"
            . "• *Alamat Kantor:* Balai Kota Banda Aceh (Gedung C Lantai 3), Jl. Tgk. Abu Lam U No. 7, Banda Aceh";

        return [
            'answer' => $emergencyAnswer,
            'is_fallback' => true,
            'sources' => [],
            'source_type' => 'maintenance_fallback',
        ];
    }

    /**
     * Memeriksa apakah teks kueri cocok dengan kata kunci atau judul.
     */
    protected static function matchesKeywords(string $queryLower, ?string $keywords, ?string $title): bool
    {
        if ($title && str_contains($queryLower, strtolower($title))) {
            return true;
        }

        if (empty($keywords)) {
            return false;
        }

        $kwList = preg_split('/[,\n|;]+/', strtolower($keywords));
        foreach ($kwList as $kw) {
            $kw = trim($kw);
            if (empty($kw)) {
                continue;
            }

            // Exact word or substring match
            if (str_contains($queryLower, $kw) || str_contains($kw, $queryLower)) {
                return true;
            }
        }

        return false;
    }
}
