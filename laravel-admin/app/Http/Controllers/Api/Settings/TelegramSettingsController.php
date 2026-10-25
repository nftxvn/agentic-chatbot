<?php

namespace App\Http\Controllers\Api\Settings;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use App\Services\Settings\ChannelSettingsService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;

class TelegramSettingsController extends Controller
{
    public function __construct(private ChannelSettingsService $settings)
    {
    }

    public function getTelegramSettings()
    {
        return response()->json($this->settings->getTelegram());
    }

    /**
     * Save/Update Telegram settings
     */
    public function updateTelegramSettings(Request $request)
    {
        $rawToken = trim($request->input('telegram_bot_token', ''));
        $rawUsername = trim($request->input('telegram_bot_username', ''));

        $request->merge([
            'telegram_bot_token' => !empty($rawToken) ? $rawToken : null,
            'telegram_bot_username' => !empty($rawUsername) ? $rawUsername : null,
        ]);

        $validated = $request->validate([
            'telegram_status' => 'required|boolean',
            'telegram_bot_token' => 'nullable|string',
            'telegram_bot_username' => 'nullable|string|max:100',
        ]);

        $this->settings->updateTelegram($validated);

        return response()->json([
            'success' => true,
            'message' => 'Pengaturan Telegram berhasil disimpan.',
            'telegram_bot_username' => AppSetting::getVal('telegram_bot_username', ''),
        ]);
    }

    /**
     * Test Telegram Connection or send a test message
     */
    public function testTelegramConnection(Request $request)
    {
        $validated = $request->validate([
            'chat_id' => 'nullable|string|max:50',
            'test_message' => 'nullable|string|max:500',
        ]);

        $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
        if (empty($encryptedToken)) {
            return response()->json([
                'success' => false,
                'message' => 'Bot Token Telegram belum dikonfigurasi.',
            ], 422);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal mendekripsi Bot Token Telegram.',
            ], 500);
        }

        $chatId = $validated['chat_id'] ?? null;
        $message = $validated['test_message'] ?? "Halo! Ini adalah pesan uji coba koneksi Telegram Bot resmi Layanan Informasi Diskominfotik Kota Banda Aceh.";

        try {
            if (empty($chatId)) {
                // Test getMe only
                $response = \Illuminate\Support\Facades\Http::timeout(10)->get("https://api.telegram.org/bot{$token}/getMe");
                if ($response->successful() && $response->json('ok')) {
                    $bot = $response->json('result');
                    return response()->json([
                        'success' => true,
                        'message' => "Koneksi berhasil! Bot teridentifikasi: {$bot['first_name']} (@{$bot['username']})",
                        'bot_info' => $bot,
                    ]);
                }
                return response()->json([
                    'success' => false,
                    'message' => 'Telegram Bot API menolak token: ' . ($response->json('description') ?? $response->body()),
                ], 422);
            }

            // Test send message
            $response = \Illuminate\Support\Facades\Http::timeout(15)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                'chat_id' => $chatId,
                'text' => $message,
                'parse_mode' => 'Markdown',
            ]);

            if ($response->successful() && $response->json('ok')) {
                return response()->json([
                    'success' => true,
                    'message' => "Pesan uji coba berhasil terkirim ke Chat ID {$chatId}.",
                    'response' => $response->json('result'),
                ]);
            }

            return response()->json([
                'success' => false,
                'message' => 'Telegram API merespon: ' . ($response->json('description') ?? $response->body()),
            ], 502);

        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal terhubung ke Telegram API: ' . $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Register or Unregister Webhook directly to Telegram API
     */
    public function setTelegramWebhook(Request $request)
    {
        $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
        if (empty($encryptedToken)) {
            return response()->json([
                'success' => false,
                'message' => 'Bot Token Telegram belum dikonfigurasi.',
            ], 422);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal mendekripsi Bot Token Telegram.',
            ], 500);
        }

        $webhookUrl = trim($request->input('webhook_url', '')) ?: url('/api/v1/webhook/telegram');
        $action = $request->input('action', 'set');

        if ($action !== 'delete') {
            if (!str_starts_with(strtolower($webhookUrl), 'https://')) {
                return response()->json([
                    'success' => false,
                    'message' => 'Telegram mewajibkan URL Webhook berawalan HTTPS yang dapat diakses dari internet (contoh: https://domain-anda.com/... atau https://xxx.ngrok-free.app/...). Untuk pengujian lokal di laptop, gunakan mode Polling: "php artisan telegram:poll".',
                ], 422);
            }
        }

        try {
            if ($action === 'delete') {
                $response = \Illuminate\Support\Facades\Http::timeout(10)->post("https://api.telegram.org/bot{$token}/deleteWebhook");
            } else {
                $response = \Illuminate\Support\Facades\Http::timeout(10)->post("https://api.telegram.org/bot{$token}/setWebhook", [
                    'url' => $webhookUrl,
                ]);
            }

            if ($response->successful() && $response->json('ok')) {
                return response()->json([
                    'success' => true,
                    'message' => $action === 'delete' ? 'Webhook Telegram berhasil dinonaktifkan.' : "Webhook berhasil didaftarkan ke Telegram: {$webhookUrl}",
                    'telegram_response' => $response->json(),
                ]);
            }

            $errMsg = $response->json('description') ?? $response->body();
            if ($response->status() === 401 || str_contains(strtolower($errMsg), 'unauthorized')) {
                $errMsg = 'Token Bot Telegram salah atau belum disimpan di Web Admin. Silakan periksa kembali Token dari @BotFather lalu klik "Simpan Kredensial Telegram".';
            }

            return response()->json([
                'success' => false,
                'message' => 'Telegram menolak pendaftaran webhook: ' . $errMsg,
            ], 422);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal menghubungi Telegram: ' . $e->getMessage(),
            ], 500);
        }
    }
}
