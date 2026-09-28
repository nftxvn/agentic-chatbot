<?php

namespace App\Console\Commands;

use App\Models\AppSetting;
use App\Models\ChatTicket;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
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

                    $rawName = trim(preg_replace('/[.\s]+/', ' ', $fromName ?? ''));
                    $displayName = !empty($rawName) ? $rawName : 'Warga';

                    if (!$chatId) {
                        continue;
                    }

                    // Deteksi Lampiran Foto atau Dokumen Gambar
                    $photoArray = $message['photo'] ?? null;
                    $docObj = $message['document'] ?? null;
                    $photoFileId = null;

                    if (!empty($photoArray) && is_array($photoArray)) {
                        $bestPhoto = end($photoArray);
                        $photoFileId = $bestPhoto['file_id'] ?? null;
                    } elseif (!empty($docObj) && str_starts_with($docObj['mime_type'] ?? '', 'image/')) {
                        $photoFileId = $docObj['file_id'] ?? null;
                    }

                    // Tangani pesan non-teks tanpa gambar (stiker, audio, voice, kontak)
                    if (empty($text) && empty($photoFileId)) {
                        $this->line("[Telegram] Pesan non-teks dari {$displayName} (Chat ID: {$chatId}). Mengirim petunjuk format...");
                        try {
                            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                                'chat_id' => $chatId,
                                'text' => "Halo {$displayName}! Saat ini Asisten Virtual Diskominfotik baru dapat melayani pertanyaan dalam bentuk pesan teks dan foto/tangkapan layar.\n\nSilakan ketik pertanyaan Anda atau kirimkan screenshot kendala.",
                            ]);
                        } catch (\Exception $e) {
                            // Ignore
                        }
                        continue;
                    }

                    // Normalisasi command /start, /reset, atau /help
                    if ($text === '/start' || $text === '/reset' || $text === '/help') {
                        // Bersihkan sesi memori AI di Redis agar dimulai dari lembaran baru
                        try {
                            \Illuminate\Support\Facades\Redis::connection()->select(2);
                            \Illuminate\Support\Facades\Redis::del("chatbot:session:telegram-{$chatId}");
                        } catch (\Exception $e) {
                            // Ignore
                        }
                        $text = 'Halo';
                    }

                    $this->line("[Telegram] Pesan dari {$fromName} (Chat ID: {$chatId})" . (!empty($photoFileId) ? ' [Lampiran Foto]' : '') . ": {$text}");

                    if (!$isActive) {
                        $this->warn('  -> Status Telegram sedang Nonaktif di Web Admin. Pesan diabaikan.');
                        continue;
                    }

                    $sessionId = 'telegram-' . $chatId;

                    // Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
                    $activeTicket = ChatTicket::where('session_id', $sessionId)
                        ->whereIn('status', ['open', 'in_progress'])
                        ->latest('id')
                        ->first();

                    // 1. KONDISI: Ada Tiket Aktif (Pesan Teks / Foto langsung diteruskan ke Petugas)
                    if ($activeTicket) {
                        // Auto-enrich ticket metadata (Nama, Instansi, Kendala) from ongoing message
                        \App\Services\EntityExtractorService::enrichTicket($activeTicket, $text, $fromName);

                        if (empty($activeTicket->citizen_contact)) {
                            $activeTicket->citizen_contact = $username ? "@{$username} (ID: {$chatId})" : "ID: {$chatId}";
                        }

                        $senderDisplayName = $activeTicket->citizen_name ?: ($fromName ?: 'Warga Telegram');

                        $attachments = [];
                        if (!empty($photoFileId)) {
                            $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $activeTicket->id, $text);
                            if ($att) {
                                $attachments[] = $att;
                            }
                        }

                        $msgText = !empty($text) ? $text : (!empty($attachments) ? '[Lampiran Foto]' : '-');

                        $msg = $activeTicket->messages()->create([
                            'sender_type' => 'citizen',
                            'sender_id' => null,
                            'sender_name' => $senderDisplayName,
                            'message' => $msgText,
                            'attachments' => !empty($attachments) ? $attachments : null,
                            'is_internal_note' => false,
                        ]);

                        $activeTicket->last_message_at = now();
                        $activeTicket->save();

                        event(new TicketMessageSent($msg));
                        event(new TicketUpdated($activeTicket));

                        $this->info("  -> [Human Takeover] Tiket aktif #{$activeTicket->ticket_number} terdeteksi. Pesan " . (!empty($attachments) ? '& Foto ' : '') . "diteruskan ke Live Chat Petugas.");
                        continue;
                    }

                    // 2. KONDISI: User Mengirim FOTO saat belum ada tiket aktif
                    // -> Foto HANYA diproses oleh Petugas (Bypass AI 100%, Otomatis Buat / Buka Tiket)
                    if (!empty($photoFileId)) {
                        $this->info("  -> [Foto Masuk] Foto hanya diproses oleh Petugas. Membuka tiket Live Chat baru/re-open...");

                        // Cek apakah ada tiket sesi ini hari ini untuk di-reopen
                        $existingToday = ChatTicket::where('session_id', $sessionId)
                            ->whereDate('created_at', today())
                            ->latest('id')
                            ->first();

                        $targetTicket = null;

                        if ($existingToday) {
                            $existingToday->status = 'in_progress';
                            $existingToday->resolved_at = null;
                            $existingToday->closed_at = null;
                            $existingToday->last_message_at = now();
                            $existingToday->save();

                            $reopenMsg = $existingToday->messages()->create([
                                'sender_type' => 'system',
                                'sender_id' => null,
                                'sender_name' => 'Sistem Helpdesk',
                                'message' => "Ticket Re-opened: {$existingToday->ticket_number}",
                                'is_internal_note' => false,
                            ]);
                            event(new TicketMessageSent($reopenMsg));

                            $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $existingToday->id, $text);
                            $msg = $existingToday->messages()->create([
                                'sender_type' => 'citizen',
                                'sender_id' => null,
                                'sender_name' => $displayName,
                                'message' => !empty($text) ? $text : '[Lampiran Foto]',
                                'attachments' => $att ? [$att] : null,
                                'is_internal_note' => false,
                            ]);

                            event(new TicketMessageSent($msg));
                            event(new TicketUpdated($existingToday));
                            $targetTicket = $existingToday;
                        } else {
                            $newTicket = ChatTicket::create([
                                'session_id' => $sessionId,
                                'citizen_name' => $displayName,
                                'citizen_contact' => (string) $chatId,
                                'citizen_agency' => $username ? "@{$username}" : null,
                                'channel' => 'telegram',
                                'status' => 'open',
                                'priority' => 'medium',
                                'issue_summary' => !empty($text) ? $text : 'Lampiran foto kendala warga via Telegram',
                                'last_message_at' => now(),
                            ]);

                            $openMsg = $newTicket->messages()->create([
                                'sender_type' => 'system',
                                'sender_id' => null,
                                'sender_name' => 'Sistem Helpdesk',
                                'message' => "Ticket Opened: {$newTicket->ticket_number}",
                                'is_internal_note' => false,
                            ]);

                            event(new \App\Events\TicketCreated($newTicket));
                            event(new TicketMessageSent($openMsg));

                            $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $newTicket->id, $text);
                            $msg = $newTicket->messages()->create([
                                'sender_type' => 'citizen',
                                'sender_id' => null,
                                'sender_name' => $displayName,
                                'message' => !empty($text) ? $text : '[Lampiran Foto]',
                                'attachments' => $att ? [$att] : null,
                                'is_internal_note' => false,
                            ]);

                            event(new TicketMessageSent($msg));
                            event(new TicketUpdated($newTicket));
                            $targetTicket = $newTicket;
                        }

                        // Kirim konfirmasi tiket ke Telegram warga
                        try {
                            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                                'chat_id' => $chatId,
                                'text' => "Halo {$displayName}! Foto tangkapan layar kendala Anda telah kami teruskan ke Petugas Live Chat Helpdesk (Tiket #{$targetTicket->ticket_number}).\n\nPetugas kami akan segera meninjau dan merespons Anda di sini.",
                            ]);
                        } catch (\Exception $e) {
                            // Ignore
                        }

                        $this->info("  -> Tiket #{$targetTicket->ticket_number} berhasil diterbitkan & foto dikirim ke dashboard Petugas.");
                        continue;
                    }

                    // 3. KONDISI: Pesan TEKS biasa saat belum ada tiket -> Masuk ke Asisten AI (RAG)
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
                // Tangani timeout atau DNS failure secara elegan
                $errorMsg = $e->getMessage();
                if (!str_contains($errorMsg, 'cURL error 28')) {
                    $this->warn('Warning Polling Connection: ' . $errorMsg);
                    // Jika DNS lookup gagal (error 6) atau network down, berikan jeda backoff agar tidak spam
                    if (str_contains($errorMsg, 'cURL error 6') || str_contains($errorMsg, 'Could not resolve host')) {
                        sleep(3);
                    }
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
}
