<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
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

        // 1. Anti-Looping / Deduplikasi Update Telegram (Mencegah retry otomatis Telegram saat respon AI > 5 detik)
        $updateId = $request->input('update_id');
        if ($updateId) {
            $lockKey = "telegram:update:{$updateId}";
            if (!Cache::add($lockKey, 1, 180)) {
                Log::info("Pesan Telegram duplikat diabaikan (Update ID #{$updateId} sedang/sudah diproses).");
                return response()->json(['status' => 'ignored', 'reason' => 'duplicate_update_id']);
            }
        }

        $chatId = $request->input('message.chat.id') ?? $request->input('edited_message.chat.id');
        $messageId = $request->input('message.message_id') ?? $request->input('edited_message.message_id');
        $messageText = trim($request->input('message.text') ?? $request->input('message.caption') ?? '');
        $fromName = $request->input('message.from.first_name', 'User');

        if ($chatId && $messageId) {
            $msgLockKey = "telegram:msg:{$chatId}:{$messageId}";
            if (!Cache::add($msgLockKey, 1, 180)) {
                Log::info("Pesan Telegram duplikat diabaikan (Chat #{$chatId}, Msg #{$messageId}).");
                return response()->json(['status' => 'ignored', 'reason' => 'duplicate_message_id']);
            }
        }

        if (empty($chatId) || empty($messageText)) {
            return response()->json(['status' => 'ignored', 'reason' => 'no_text_or_chat_id']);
        }

        if ($messageText === '/start' || $messageText === '/reset' || $messageText === '/help') {
            try {
                \Illuminate\Support\Facades\Redis::connection()->select(2);
                \Illuminate\Support\Facades\Redis::del("chatbot:session:telegram-{$chatId}");
            } catch (\Exception $e) {
                // Ignore
            }
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
        $sessionId = 'telegram-' . $chatId;

        // 3. Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = \App\Models\ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        if ($activeTicket) {
            // Auto-enrich ticket metadata (Nama, Instansi, Kendala) from ongoing message
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $messageText, $fromName);

            if (empty($activeTicket->citizen_contact)) {
                $activeTicket->citizen_contact = $fromUsername ? "@{$fromUsername} (ID: {$chatId})" : "ID: {$chatId}";
            }

            $senderDisplayName = $activeTicket->citizen_name ?: ($fromName ?: 'Warga Telegram');

            $msg = $activeTicket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $senderDisplayName,
                'message' => $messageText,
                'is_internal_note' => false,
            ]);

            $activeTicket->last_message_at = now();
            $activeTicket->save();

            event(new \App\Events\TicketMessageSent($msg));
            event(new \App\Events\TicketUpdated($activeTicket));

            Log::info('Pesan Telegram diteruskan langsung ke Live Chat (Human Takeover)', [
                'ticket_id' => $activeTicket->id,
                'chat_id' => $chatId,
                'from' => $senderDisplayName,
                'message' => substr($messageText, 0, 80),
            ]);

            return response()->json([
                'status' => 'forwarded_to_live_chat',
                'ticket_id' => $activeTicket->id,
            ]);
        }

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
            'citizen_name' => $fromName,
            'citizen_contact' => $fromUsername ? "@{$fromUsername} (ID: {$chatId})" : (string) $chatId,
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
}
