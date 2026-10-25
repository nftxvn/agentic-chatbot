<?php

namespace App\Services\Channels;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class TelegramAiResponder
{
    public function __construct(private AiChatGateway $ai)
    {
    }

    public function replyToWebhook(string $token, int|string $chatId, string $text, string $aiBaseUrl, string $aiToken, string $fromName = 'User', ?string $fromUsername = null): void
    {
        $startTime = $this->timestamp();

        // 1. Tampilkan status 'typing' di header Telegram
        try {
            Http::timeout(5)->post("https://api.telegram.org/bot{$token}/sendChatAction", [
                'chat_id' => $chatId,
                'action' => 'typing',
            ]);
        } catch (\Exception $e) {
            // Ignore
        }

        // 2. Kirim pesan placeholder awal yang ramah dan manusiawi
        $messageId = null;
        try {
            $initRes = Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                'chat_id' => $chatId,
                'text' => 'Baik, mohon ditunggu sebentar ya, sedang kami siapkan informasinya...',
            ]);
            if ($initRes->successful() && $initRes->json('ok')) {
                $messageId = $initRes->json('result.message_id');
            }
        } catch (\Exception $e) {
            Log::warning('Gagal mengirim pesan awal Telegram: ' . $e->getMessage());
        }

        $accumulated = '';
        $lastEditTime = $this->timestamp();
        $lastSentLength = 0;
        $sseBuffer = '';

        // 3. Panggil Python AI /api/chat/stream via cURL
        $curlError = $this->ai->stream(
            rtrim($aiBaseUrl, '/') . '/api/chat/stream', $aiToken,
            [
                'query' => $text,
                'session_id' => 'telegram-' . $chatId,
                'citizen_name' => $fromName,
                'citizen_contact' => $fromUsername ? "@{$fromUsername} (ID: {$chatId})" : (string) $chatId,
            ],
            function ($ch, $chunk) use (
                &$accumulated, &$sseBuffer, &$lastEditTime, &$lastSentLength, $messageId, $token, $chatId
            ) {
                $sseBuffer .= $chunk;
                while (($pos = strpos($sseBuffer, "\n")) !== false) {
                    $line = trim(substr($sseBuffer, 0, $pos));
                    $sseBuffer = substr($sseBuffer, $pos + 1);

                    if (str_starts_with($line, 'data:')) {
                        $jsonStr = trim(substr($line, 5));
                        $data = json_decode($jsonStr, true);
                        if (is_array($data)) {
                            $type = $data['type'] ?? '';
                            if ($type === 'chunk') {
                                $accumulated .= $data['content'] ?? '';
                                $now = $this->timestamp();

                                // Throttle Telegram edits: minimal 1.2 detik jeda dan ada penambahan minimal 20 karakter
                                if ($messageId && ($now - $lastEditTime) >= 1.2 && (strlen($accumulated) - $lastSentLength) >= 20) {
                                    $lastEditTime = $now;
                                    $lastSentLength = strlen($accumulated);

                                    // Kirim draft teks dengan kursor pengetikan
                                    try {
                                        Http::timeout(5)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                                            'chat_id' => $chatId,
                                            'message_id' => $messageId,
                                            'text' => $accumulated . "\n\n▌",
                                        ]);
                                    } catch (\Exception $e) {
                                        // Ignore throttling errors
                                    }
                                }
                            }
                        }
                    }
                }
                return strlen($chunk);
            },
        );

        if (empty(trim($accumulated))) {
            if ($curlError) {
                Log::warning('AI Service offline/unreachable on Telegram webhook, applying graceful degradation: ' . $curlError);
            }
            $fallback = \App\Services\GracefulDegradationService::resolveFallback($text);
            $accumulated = $fallback['answer'];

            if (!empty($fallback['sources'])) {
                $sourceLines = [];
                foreach ($fallback['sources'] as $s) {
                    $docName = $s['doc_name'] ?? 'Dokumen Resmi';
                    $page = isset($s['page']) ? "Halaman {$s['page']}" : null;
                    $sourceLines[] = "• " . $docName . ($page ? " ({$page})" : '');
                }
                $accumulated .= "\n\n*Sumber Referensi Dokumen:*\n" . implode("\n", $sourceLines);
            }
        }

        // 4. Kirim hasil final dengan format Markdown
        if ($messageId) {
            try {
                $finalRes = Http::timeout(10)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                    'chat_id' => $chatId,
                    'message_id' => $messageId,
                    'text' => $accumulated,
                    'parse_mode' => 'Markdown',
                ]);

                // Fallback jika Markdown gagal diparsing oleh Telegram
                if (!$finalRes->successful()) {
                    Http::timeout(10)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                        'chat_id' => $chatId,
                        'message_id' => $messageId,
                        'text' => $accumulated,
                    ]);
                }
            } catch (\Exception $e) {
                Log::error('Gagal memperbarui pesan final webhook Telegram: ' . $e->getMessage());
            }
        } else {
            try {
                $finalRes = Http::timeout(15)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                    'chat_id' => $chatId,
                    'text' => $accumulated,
                    'parse_mode' => 'Markdown',
                ]);
                if (!$finalRes->successful()) {
                    Http::timeout(15)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                        'chat_id' => $chatId,
                        'text' => $accumulated,
                    ]);
                }
            } catch (\Exception $e) {
                Log::error('Gagal mengirim pesan final webhook Telegram: ' . $e->getMessage());
            }
        }

        // 5. Catat interaksi ke ChatLog
        $elapsedMs = (int) round(($this->timestamp() - $startTime) * 1000);
        $isFallback = empty(trim($accumulated))
            || str_contains(strtolower($accumulated), 'terhubung dengan petugas')
            || str_contains(strtolower($accumulated), 'menindaklanjuti pesan')
            || str_contains(strtolower($accumulated), 'menindaklanjuti percakapan');

        $senderIdentifier = !empty($fromUsername)
            ? "{$fromName} (@{$fromUsername}, ID: {$chatId})"
            : "{$fromName} (ID: {$chatId})";

        try {
            \App\Models\ChatLog::create([
                'session_id' => 'telegram-' . $chatId,
                'channel' => 'telegram',
                'api_key_id' => null,
                'sender_identifier' => 'Pengguna Telegram',
                'query' => null,
                'answer' => null,
                'sources_json' => null,
                'is_fallback' => $isFallback,
                'response_time_ms' => $elapsedMs,
            ]);
        } catch (\Exception $e) {
            Log::error('Gagal mencatat telemetri Telegram ke ChatLog: ' . $e->getMessage());
        }
    }

    public function replyToPolling(string $token, int|string $chatId, string $text, string $fromName, ?string $username, string $aiBaseUrl, string $aiToken, ?callable $logger = null): void
    {
        $startTime = $this->timestamp();

        // 1. Tampilkan status 'typing' di header Telegram
        try {
            Http::timeout(5)->post("https://api.telegram.org/bot{$token}/sendChatAction", [
                'chat_id' => $chatId,
                'action' => 'typing',
            ]);
        } catch (\Exception $e) {
            // Ignore
        }

        // 2. Kirim pesan placeholder awal yang ramah dan manusiawi
        $messageId = null;
        try {
            $initRes = Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                'chat_id' => $chatId,
                'text' => 'Baik, mohon ditunggu sebentar ya, sedang kami siapkan informasinya...',
            ]);
            if ($initRes->successful() && $initRes->json('ok')) {
                $messageId = $initRes->json('result.message_id');
            }
        } catch (\Exception $e) {
            if ($logger) $logger('warn', 'Gagal mengirim pesan awal Telegram: ' . $e->getMessage());
        }

        $accumulated = '';
        $lastEditTime = $this->timestamp();
        $lastSentLength = 0;
        $sseBuffer = '';

        // 3. Panggil Python AI /api/chat/stream via cURL
        $curlError = $this->ai->stream(
            rtrim($aiBaseUrl, '/') . '/api/chat/stream', $aiToken,
            [
                'query' => $text,
                'session_id' => 'telegram-' . $chatId,
            ],
            function ($ch, $chunk) use (
                &$accumulated, &$sseBuffer, &$lastEditTime, &$lastSentLength, $messageId, $token, $chatId, $logger
            ) {
                $sseBuffer .= $chunk;
                while (($pos = strpos($sseBuffer, "\n")) !== false) {
                    $line = trim(substr($sseBuffer, 0, $pos));
                    $sseBuffer = substr($sseBuffer, $pos + 1);

                    if (str_starts_with($line, 'data:')) {
                        $jsonStr = trim(substr($line, 5));
                        $data = json_decode($jsonStr, true);
                        if (is_array($data)) {
                            $type = $data['type'] ?? '';
                            if ($type === 'chunk') {
                                $accumulated .= $data['content'] ?? '';
                                $now = $this->timestamp();

                                // Throttle Telegram edits: minimal 1.5 detik jeda dan ada penambahan minimal 25 karakter
                                if ($messageId && ($now - $lastEditTime) >= 1.5 && (strlen($accumulated) - $lastSentLength) >= 25) {
                                    $lastEditTime = $now;
                                    $lastSentLength = strlen($accumulated);

                                    // Kirim draft teks dengan kursor pengetikan
                                    try {
                                        Http::timeout(5)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                                            'chat_id' => $chatId,
                                            'message_id' => $messageId,
                                            'text' => $accumulated . "\n\n▌",
                                        ]);
                                    } catch (\Exception $e) {
                                        // Ignore throttling errors
                                    }
                                }
                            }
                        }
                    }
                }
                return strlen($chunk);
            },
        );

        if (empty(trim($accumulated))) {
            if ($curlError && $logger) {
                $logger('warn', 'AI Engine offline/unreachable, mengaktifkan Graceful Degradation: ' . $curlError);
            }
            $fallback = \App\Services\GracefulDegradationService::resolveFallback($text);
            $accumulated = $fallback['answer'];

            if (!empty($fallback['sources'])) {
                $sourceLines = [];
                foreach ($fallback['sources'] as $s) {
                    $docName = $s['doc_name'] ?? 'Dokumen Resmi';
                    $page = isset($s['page']) ? "Halaman {$s['page']}" : null;
                    $sourceLines[] = "• " . $docName . ($page ? " ({$page})" : '');
                }
                $accumulated .= "\n\n*Sumber Referensi Dokumen:*\n" . implode("\n", $sourceLines);
            }
        }

        // 4. Kirim hasil final dengan format rapi
        $finalSent = false;
        if ($messageId) {
            try {
                // Coba 1: Edit pesan dengan Markdown
                $finalRes = Http::timeout(10)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                    'chat_id' => $chatId,
                    'message_id' => $messageId,
                    'text' => $accumulated,
                    'parse_mode' => 'Markdown',
                ]);

                if ($finalRes->successful() && $finalRes->json('ok')) {
                    $finalSent = true;
                } else {
                    // Coba 2: Edit pesan tanpa Markdown jika Markdown gagal diparse Telegram
                    $plainRes = Http::timeout(10)->post("https://api.telegram.org/bot{$token}/editMessageText", [
                        'chat_id' => $chatId,
                        'message_id' => $messageId,
                        'text' => $accumulated,
                    ]);
                    if ($plainRes->successful() && $plainRes->json('ok')) {
                        $finalSent = true;
                    }
                }
            } catch (\Exception $e) {
                if ($logger) $logger('warn', 'Gagal memperbarui pesan via editMessageText: ' . $e->getMessage());
            }
        }

        // Fallback: Kirim pesan baru jika edit pesan gagal atau message_id awal tidak ada
        if (!$finalSent) {
            try {
                $newRes = Http::timeout(15)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                    'chat_id' => $chatId,
                    'text' => $accumulated,
                    'parse_mode' => 'Markdown',
                ]);
                if (!$newRes->successful()) {
                    Http::timeout(15)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                        'chat_id' => $chatId,
                        'text' => $accumulated,
                    ]);
                }
            } catch (\Exception $e) {
                if ($logger) $logger('error', 'Gagal mengirim balasan final: ' . $e->getMessage());
            }
        }

        // 5. Catat interaksi ke ChatLog
        $elapsedMs = (int) round(($this->timestamp() - $startTime) * 1000);
        $isFallback = empty(trim($accumulated))
            || str_contains(strtolower($accumulated), 'terhubung dengan petugas')
            || str_contains(strtolower($accumulated), 'menindaklanjuti pesan')
            || str_contains(strtolower($accumulated), 'menindaklanjuti percakapan');

        $senderIdentifier = !empty($username)
            ? "{$fromName} (@{$username}, ID: {$chatId})"
            : "{$fromName} (ID: {$chatId})";

        try {
            \App\Models\ChatLog::create([
                'session_id' => 'telegram-' . $chatId,
                'channel' => 'telegram',
                'api_key_id' => null,
                'sender_identifier' => 'Pengguna Telegram',
                'query' => null,
                'answer' => null,
                'sources_json' => null,
                'is_fallback' => $isFallback,
                'response_time_ms' => $elapsedMs,
            ]);
            if ($logger) {
                $logger('info', "Telemetri interaksi tercatat di database (durasi: {$elapsedMs} ms, privasi aman).");
            }
        } catch (\Exception $e) {
            Log::error('Gagal mencatat telemetri Telegram ke ChatLog: ' . $e->getMessage());
            if ($logger) {
                $logger('warn', 'Gagal mencatat telemetri: ' . $e->getMessage());
            }
        }
    }

    protected function timestamp(): float
    {
        return microtime(true);
    }
}
