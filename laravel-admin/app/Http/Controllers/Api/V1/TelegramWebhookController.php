<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class TelegramWebhookController extends Controller
{
    /**
     * Get Python AI backend base URL
     */
    protected function getAiBaseUrl(): string
    {
        return config('services.ai.url', 'http://localhost:8080');
    }

    /**
     * Token internal untuk memanggil layanan Python AI.
     */
    protected function getInternalToken(): string
    {
        return (string) config('services.ai_microservice.token');
    }

    /**
     * POST /api/v1/webhook/telegram — Handle Inbound Telegram Updates
     */
    public function handle(Request $request)
    {
        $isActive = AppSetting::getVal('telegram_status', 'false') === 'true';
        if (!$isActive) {
            Log::info('Pesan Telegram diabaikan karena status Telegram bot sedang nonaktif.');
            return response()->json(['status' => 'ignored', 'reason' => 'telegram_disabled']);
        }

        $chatId = $request->input('message.chat.id');
        $messageText = $request->input('message.text');
        $fromName = $request->input('message.from.first_name', 'User');

        if (empty($chatId) || empty($messageText)) {
            return response()->json(['status' => 'ignored', 'reason' => 'no_text_or_chat_id']);
        }

        if (trim($messageText) === '/start') {
            $messageText = 'Halo';
        }

        Log::info('Pesan Telegram Masuk', [
            'chat_id' => $chatId,
            'from' => $fromName,
            'message' => substr($messageText, 0, 80),
        ]);

        $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
        if (empty($encryptedToken)) {
            Log::error('Bot Token Telegram belum dikonfigurasi saat webhook dipanggil.');
            return response()->json(['status' => 'error', 'reason' => 'missing_bot_token']);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            Log::error('Gagal mendekripsi Bot Token Telegram: ' . $e->getMessage());
            return response()->json(['status' => 'error', 'reason' => 'decrypt_failed']);
        }

        $fromUsername = $request->input('message.from.username');

        $this->streamAiToTelegram($token, $chatId, $messageText, $fromName, $fromUsername);

        return response()->json(['status' => 'success']);
    }

    /**
     * Memproses respon AI secara streaming dan memperbarui pesan di Telegram secara real-time.
     */
    protected function streamAiToTelegram(string $token, int|string $chatId, string $text, string $fromName = 'User', ?string $fromUsername = null): void
    {
        $startTime = microtime(true);
        $aiBaseUrl = $this->getAiBaseUrl();
        $aiToken = $this->getInternalToken();

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
        $lastEditTime = microtime(true);
        $lastSentLength = 0;
        $sseBuffer = '';

        // 3. Panggil Python AI /api/chat/stream via cURL
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, rtrim($aiBaseUrl, '/') . '/api/chat/stream');
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
            'query' => $text,
            'session_id' => 'telegram-' . $chatId,
        ]));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Authorization: Bearer ' . $aiToken,
            'Content-Type: application/json',
            'Accept: text/event-stream',
        ]);
        curl_setopt($ch, CURLOPT_TIMEOUT, 120);
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($ch, $chunk) use (
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
                            $now = microtime(true);

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
        });

        curl_exec($ch);
        $curlError = curl_error($ch);
        curl_close($ch);

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
        $elapsedMs = (int) round((microtime(true) - $startTime) * 1000);
        $isFallback = empty(trim($accumulated))
            || str_contains(strtolower($accumulated), 'tidak ditemukan')
            || str_contains(strtolower($accumulated), 'belum termuat')
            || str_contains(strtolower($accumulated), 'tidak ada di dalam dokumen');

        $senderIdentifier = !empty($fromUsername)
            ? "{$fromName} (@{$fromUsername}, ID: {$chatId})"
            : "{$fromName} (ID: {$chatId})";

        try {
            \App\Models\ChatLog::create([
                'session_id' => 'telegram-' . $chatId,
                'channel' => 'telegram',
                'api_key_id' => null,
                'sender_identifier' => $senderIdentifier,
                'query' => $text,
                'answer' => $accumulated,
                'sources_json' => null,
                'is_fallback' => $isFallback,
                'response_time_ms' => $elapsedMs,
            ]);
        } catch (\Exception $e) {
            Log::error('Gagal mencatat audit log Telegram ke ChatLog: ' . $e->getMessage());
        }
    }
}
