<?php

namespace App\Console\Commands;

use App\Models\AppSetting;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class TelegramPollCommand extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'telegram:poll {--once : Hanya jalankan satu kali batch update}';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Jalankan Telegram Bot Runner via Long Polling (cocok untuk lokal/laptop tanpa IP publik/ngrok)';

    /**
     * Execute the console command.
     */
    public function handle()
    {
        $this->info('────────────────────────────────────────────────────────────');
        $this->info('  TELEGRAM BOT RUNNER — DISKOMINFOTIK BANDA ACEH');
        $this->info('  Mode: Real-time Long Polling (Lokal Laptop / Server)');
        $this->info('────────────────────────────────────────────────────────────');

        $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
        if (empty($encryptedToken)) {
            $this->error('Error: Bot Token Telegram belum dikonfigurasi di Web Admin!');
            $this->warn('Silakan masukkan token dari @BotFather di menu Integrasi & API Web Admin.');
            return 1;
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            $this->error('Error: Gagal mendekripsi Bot Token Telegram dari database.');
            return 1;
        }

        // Verifikasi token via getMe
        $this->info('Memverifikasi token bot ke Telegram...');
        try {
            $meRes = Http::timeout(10)->get("https://api.telegram.org/bot{$token}/getMe");
            if (!$meRes->successful() || !$meRes->json('ok')) {
                $this->error('Error dari Telegram: ' . ($meRes->json('description') ?? 'Unauthorized token'));
                return 1;
            }
            $botInfo = $meRes->json('result');
            $botName = $botInfo['first_name'] ?? 'Bot';
            $botUser = '@' . ($botInfo['username'] ?? 'unknown');
            $this->info("Bot Aktif: {$botName} ({$botUser})");
            AppSetting::setVal('telegram_bot_username', $botUser);
        } catch (\Exception $e) {
            $this->error('Gagal terhubung ke api.telegram.org: ' . $e->getMessage());
            return 1;
        }

        // Hapus Webhook agar mode getUpdates (long polling) bisa berjalan
        try {
            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/deleteWebhook");
            $this->info('Mode Webhook dinonaktifkan, beralih ke Long Polling.');
        } catch (\Exception $e) {
            // Ignore
        }

        $aiBaseUrl = config('services.ai.url', 'http://localhost:8080');
        $aiToken = (string) config('services.ai_microservice.token');

        $this->info('Menghubungkan ke Python AI Service di ' . $aiBaseUrl . '...');
        $this->info('Bot siap menerima pesan! Buka Telegram dan kirim pesan ke ' . $botUser);
        $this->line('Tekan Ctrl+C untuk menghentikan runner.');
        $this->newLine();

        $offset = 0;

        while (true) {
            // Cek status toggle secara real-time
            $isActive = AppSetting::getVal('telegram_status', 'false') === 'true';

            try {
                $response = Http::withHeaders([
                    'Connection' => 'close',
                ])->timeout(35)->get("https://api.telegram.org/bot{$token}/getUpdates", [
                    'offset' => $offset,
                    'timeout' => 20,
                    'allowed_updates' => json_encode(['message', 'edited_message']),
                ]);

                if (!$response->successful() || !$response->json('ok')) {
                    $errorCode = $response->json('error_code');
                    $desc = $response->json('description') ?? 'Network error';

                    if ($errorCode === 409) {
                        if (str_contains(strtolower($desc), 'terminated by other getupdates') || str_contains(strtolower($desc), 'one bot instance')) {
                            $this->error("Peringatan: Ada proses bot Telegram lain yang sedang berjalan secara bersamaan!");
                            $this->warn("Telegram hanya mengizinkan SATU runner aktif. Hentikan (Ctrl+C) proses runner lain terlebih dahulu.");
                            sleep(3);
                            continue;
                        }

                        $this->warn("Terdeteksi konflik Webhook aktif ({$desc}). Menghapus Webhook agar Long Polling tetap aktif...");
                        try {
                            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/deleteWebhook", [
                                'drop_pending_updates' => false,
                            ]);
                        } catch (\Exception $e) {
                            // Ignore
                        }
                    } else {
                        $this->warn("Telegram API Warning ({$errorCode}): {$desc}");
                    }
                    sleep(1);
                    continue;
                }

                $updates = $response->json('result', []);

                foreach ($updates as $update) {
                    $updateId = $update['update_id'];
                    $offset = $updateId + 1;

                    $message = $update['message'] ?? $update['edited_message'] ?? null;
                    if (!$message) {
                        continue;
                    }

                    $chatId = $message['chat']['id'] ?? null;
                    $text = trim($message['text'] ?? $message['caption'] ?? '');
                    $fromName = $message['from']['first_name'] ?? 'Pengguna';
                    $username = $message['from']['username'] ?? null;

                    if (!$chatId) {
                        continue;
                    }

                    // Tangani pesan non-teks (foto, stiker, dokumen, audio)
                    if (empty($text)) {
                        $this->line("[Telegram] Pesan non-teks dari {$fromName} (Chat ID: {$chatId}). Mengirim petunjuk format teks...");
                        try {
                            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                                'chat_id' => $chatId,
                                'text' => "Halo {$fromName}! Saat ini Asisten Virtual Diskominfotik baru dapat melayani pertanyaan dalam bentuk pesan teks.\n\nSilakan ketik pertanyaan Anda mengenai informasi SOP atau layanan kami.",
                            ]);
                        } catch (\Exception $e) {
                            // Ignore
                        }
                        continue;
                    }

                    // Normalisasi command /start atau /help
                    if ($text === '/start' || $text === '/help') {
                        $text = 'Halo';
                    }

                    $this->line("[Telegram] Pesan dari {$fromName} (Chat ID: {$chatId}): {$text}");

                    if (!$isActive) {
                        $this->warn('  -> Status Telegram sedang Nonaktif di Web Admin. Pesan diabaikan.');
                        continue;
                    }

                    $this->line('  -> Menghubungkan ke Python AI Engine (Mode Streaming)...');

                    $this->streamAiToTelegram(
                        $token,
                        $chatId,
                        $text,
                        $fromName,
                        $username,
                        $aiBaseUrl,
                        $aiToken,
                        function ($level, $msg) {
                            if ($level === 'error') $this->error("  -> {$msg}");
                            elseif ($level === 'warn') $this->warn("  -> {$msg}");
                            else $this->line("  -> {$msg}");
                        }
                    );

                    $this->info("  -> Balasan selesai distreaming ke {$fromName}!");
                }
            } catch (\Exception $e) {
                // Jangan log cURL timeout biasa (karena polling idle 20s)
                if (!str_contains($e->getMessage(), 'cURL error 28')) {
                    $this->warn('Warning Polling Connection: ' . $e->getMessage());
                }
            }

            if ($this->option('once')) {
                break;
            }

            usleep(100000); // 0.1s pause
        }

        return 0;
    }

    /**
     * Memproses respon AI secara streaming dan memperbarui pesan di Telegram secara real-time.
     */
    protected function streamAiToTelegram(string $token, int|string $chatId, string $text, string $fromName, ?string $username, string $aiBaseUrl, string $aiToken, ?callable $logger = null): void
    {
        $startTime = microtime(true);

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
                            $now = microtime(true);

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
        });

        curl_exec($ch);
        $curlError = curl_error($ch);
        curl_close($ch);

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
        $elapsedMs = (int) round((microtime(true) - $startTime) * 1000);
        $isFallback = empty(trim($accumulated))
            || str_contains(strtolower($accumulated), 'tidak ditemukan')
            || str_contains(strtolower($accumulated), 'belum termuat')
            || str_contains(strtolower($accumulated), 'tidak ada di dalam dokumen');

        $senderIdentifier = !empty($username)
            ? "{$fromName} (@{$username}, ID: {$chatId})"
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
            if ($logger) {
                $logger('info', "Riwayat percakapan tercatat di database ChatLog (durasi: {$elapsedMs} ms).");
            }
        } catch (\Exception $e) {
            Log::error('Gagal mencatat riwayat Telegram ke ChatLog: ' . $e->getMessage());
            if ($logger) {
                $logger('warn', 'Gagal mencatat log percakapan: ' . $e->getMessage());
            }
        }
    }
}
