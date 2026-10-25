<?php

namespace App\Services\Entities;

use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Redis;
use Illuminate\Support\Str;

/**
 * Pembacaan riwayat Redis dan penggabungan entitas per giliran.
 *
 * Trait dimuat pada EntityExtractorService untuk mempertahankan binding self::
 * serta properti/helper protected tanpa menyalin state atau algoritme.
 *
 * @mixin \App\Services\EntityExtractorService
 */
trait ReadsSessionEntities
{
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
        } catch (\Throwable $e) {
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
}
