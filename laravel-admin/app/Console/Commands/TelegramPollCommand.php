<?php

namespace App\Console\Commands;

use App\Models\AppSetting;
use App\Services\Channels\TelegramPollingMessageHandler;
use App\Services\Channels\TelegramAiResponder;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;

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

                    app(TelegramPollingMessageHandler::class)->handle(
                        $update, $token, $isActive, $aiBaseUrl, $aiToken,
                        fn ($level, $message) => $this->{$level}($message),
                        fn ($token, $chatId, $text, $fromName, $username, $url, $aiToken, $logger) => $this->streamAiToTelegram($token, $chatId, $text, $fromName, $username, $url, $aiToken, $logger),
                    );
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
        app(TelegramAiResponder::class)->replyToPolling($token, $chatId, $text, $fromName, $username, $aiBaseUrl, $aiToken, $logger);
    }
}
