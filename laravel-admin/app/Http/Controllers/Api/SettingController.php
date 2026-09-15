<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;

class SettingController extends Controller
{
    /**
     * Get all settings related to WhatsApp
     */
    public function getWhatsappSettings()
    {
        $rawToken = AppSetting::getVal('wa_token', '');
        $hasToken = !empty($rawToken);
        
        return response()->json([
            'wa_status' => AppSetting::getVal('wa_status', 'false') === 'true',
            'wa_api_url' => AppSetting::getVal('wa_api_url', ''),
            'wa_token' => $hasToken ? '••••••••••••' : '', // mask token when fetching
            'wa_phone_number' => AppSetting::getVal('wa_phone_number', ''),
            'wa_webhook_verify_token' => AppSetting::getVal('wa_webhook_verify_token', 'diskominfo_wa_rag_token'),
            'webhook_url' => url('/api/v1/webhook/whatsapp'),
        ]);
    }

    /**
     * Save/Update WhatsApp settings
     */
    public function updateWhatsappSettings(Request $request)
    {
        $rawApiUrl = trim($request->input('wa_api_url', ''));
        if (!empty($rawApiUrl) && !preg_match('#^https?://#i', $rawApiUrl)) {
            $rawApiUrl = 'https://' . $rawApiUrl;
        }

        $rawToken = trim($request->input('wa_token', ''));
        $rawPhone = trim($request->input('wa_phone_number', ''));
        $rawVerifyToken = trim($request->input('wa_webhook_verify_token', ''));

        $request->merge([
            'wa_api_url' => !empty($rawApiUrl) ? $rawApiUrl : null,
            'wa_token' => !empty($rawToken) ? $rawToken : null,
            'wa_phone_number' => !empty($rawPhone) ? $rawPhone : null,
            'wa_webhook_verify_token' => !empty($rawVerifyToken) ? $rawVerifyToken : null,
        ]);

        $validated = $request->validate([
            'wa_status' => 'required|boolean',
            'wa_api_url' => 'nullable|url',
            'wa_token' => 'nullable|string',
            'wa_phone_number' => 'nullable|string',
            'wa_webhook_verify_token' => 'nullable|string|max:100',
        ], [
            'wa_api_url.url' => 'URL Endpoint Gateway WhatsApp harus berupa URL yang valid (contoh: https://graph.facebook.com/... atau https://api.fonnte.com/send).',
        ]);

        AppSetting::setVal('wa_status', $validated['wa_status'] ? 'true' : 'false');
        AppSetting::setVal('wa_api_url', $validated['wa_api_url'] ?? '');
        
        // Only update token if it's provided and not masked (encrypt token at rest)
        if (isset($validated['wa_token']) && $validated['wa_token'] !== '••••••••••••') {
            $valToSave = !empty($validated['wa_token']) ? Crypt::encryptString($validated['wa_token']) : '';
            AppSetting::setVal('wa_token', $valToSave);
        } elseif (is_null($validated['wa_token'])) {
            AppSetting::setVal('wa_token', '');
        }
        
        AppSetting::setVal('wa_phone_number', $validated['wa_phone_number'] ?? '');
        AppSetting::setVal('wa_webhook_verify_token', $validated['wa_webhook_verify_token'] ?? 'diskominfo_wa_rag_token');

        return response()->json([
            'success' => true,
            'message' => 'Pengaturan WhatsApp berhasil disimpan.'
        ]);
    }

    /**
     * Test WhatsApp Gateway Connection by sending a test message
     */
    public function testWhatsappConnection(Request $request)
    {
        $validated = $request->validate([
            'target_phone' => 'required|string|min:6|max:20',
            'test_message' => 'nullable|string|max:500',
        ]);

        $apiUrl = AppSetting::getVal('wa_api_url', '');
        $encryptedToken = AppSetting::getVal('wa_token', '');

        if (empty($apiUrl) || empty($encryptedToken)) {
            return response()->json([
                'success' => false,
                'message' => 'URL API atau Access Token WhatsApp belum dikonfigurasi.',
            ], 422);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal mendekripsi token WhatsApp yang tersimpan.',
            ], 500);
        }

        $message = $validated['test_message'] ?? "Halo! Ini adalah pesan uji coba koneksi gateway WhatsApp resmi Layanan Informasi Diskominfotik Kota Banda Aceh.";
        $to = $validated['target_phone'];

        try {
            if (str_contains($apiUrl, 'graph.facebook.com')) {
                // Meta Cloud API
                $payload = [
                    'messaging_product' => 'whatsapp',
                    'recipient_type' => 'individual',
                    'to' => preg_replace('/[^0-9]/', '', $to),
                    'type' => 'text',
                    'text' => ['preview_url' => false, 'body' => $message],
                ];

                $response = \Illuminate\Support\Facades\Http::withHeaders([
                    'Authorization' => 'Bearer ' . $token,
                    'Content-Type' => 'application/json',
                ])->timeout(15)->post($apiUrl, $payload);
            } else {
                // Generic Gateway
                $payload = [
                    'target' => $to,
                    'phone' => $to,
                    'message' => $message,
                ];

                $response = \Illuminate\Support\Facades\Http::withHeaders([
                    'Authorization' => $token,
                    'Content-Type' => 'application/json',
                ])->timeout(15)->post($apiUrl, $payload);
            }

            if ($response->successful()) {
                return response()->json([
                    'success' => true,
                    'message' => "Pesan uji coba berhasil terkirim ke {$to}.",
                    'gateway_response' => $response->json(),
                ]);
            }

            return response()->json([
                'success' => false,
                'message' => 'Gateway WhatsApp merespon dengan status ' . $response->status() . ': ' . ($response->json('error.message') ?? $response->body()),
            ], 502);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal terhubung ke URL Gateway: ' . $e->getMessage(),
            ], 500);
        }
    }

    /**
     * Get all settings related to Telegram
     */
    public function getTelegramSettings()
    {
        $rawToken = AppSetting::getVal('telegram_bot_token', '');
        $hasToken = !empty($rawToken);
        $botUsername = AppSetting::getVal('telegram_bot_username', '');

        return response()->json([
            'telegram_status' => AppSetting::getVal('telegram_status', 'false') === 'true',
            'telegram_bot_token' => $hasToken ? '••••••••••••' : '',
            'telegram_bot_username' => $botUsername,
            'webhook_url' => url('/api/v1/webhook/telegram'),
        ]);
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

        AppSetting::setVal('telegram_status', $validated['telegram_status'] ? 'true' : 'false');
        AppSetting::setVal('telegram_bot_username', $validated['telegram_bot_username'] ?? '');

        // Only update token if it's provided and not masked
        if (isset($validated['telegram_bot_token']) && $validated['telegram_bot_token'] !== '••••••••••••') {
            $valToSave = !empty($validated['telegram_bot_token']) ? Crypt::encryptString($validated['telegram_bot_token']) : '';
            AppSetting::setVal('telegram_bot_token', $valToSave);

            // Try to fetch getMe to automatically discover bot username
            if (!empty($validated['telegram_bot_token'])) {
                try {
                    $getMeRes = \Illuminate\Support\Facades\Http::timeout(5)->get("https://api.telegram.org/bot{$validated['telegram_bot_token']}/getMe");
                    if ($getMeRes->successful() && $getMeRes->json('ok')) {
                        $botUser = $getMeRes->json('result.username', '');
                        if (!empty($botUser)) {
                            AppSetting::setVal('telegram_bot_username', '@' . ltrim($botUser, '@'));
                        }
                    }
                } catch (\Exception $e) {
                    // Ignore network errors
                }
            }
        } elseif (is_null($validated['telegram_bot_token'])) {
            AppSetting::setVal('telegram_bot_token', '');
        }

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

    /**
     * Default RAG System Prompt template
     */
    public static function getDefaultRagPrompt(): string
    {
        return "Anda adalah asisten virtual resmi Layanan Informasi Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh yang bertugas menjawab pertanyaan masyarakat dan ASN berdasarkan dokumen SOP kedinasan yang diberikan.\n\nKonteks Dokumen:\n{context}\n\nInstruksi Utama:\n1. Jawab selalu dalam bahasa Indonesia yang ramah, sopan, jelas, dan profesional.\n2. Jawab pertanyaan HANYA berdasarkan fakta yang tertulis di dalam Konteks Dokumen di atas. JANGAN menggunakan asumsi atau pengetahuan di luar dokumen tersebut.\n3. Dalam dokumen format SOP kedinasan/pemerintah, persyaratan berkas atau kelengkapan permohonan tercantum pada bagian 'Kelengkapan', 'Persyaratan', 'Kualifikasi Pelaksana', atau 'Pencatatan'. Bila pengguna menanyakan persyaratan/syarat, jelaskan berkas kelengkapan yang tercantum pada bagian tersebut.\n4. Bila pertanyaan menyangkut tahapan atau prosedur, jelaskan secara terstruktur menggunakan poin-poin bernomor (1, 2, 3) beserta persyaratan/kelengkapan, pelaksana, dan waktu penyelesaiannya jika tersedia.\n5. Salin nama jabatan, nomor SOP, persyaratan/kelengkapan, formulir, dan angka waktu/biaya PERSIS seperti tertulis di dokumen tanpa mengubah atau menebak.\n6. Bila konteks memuat dua aturan yang berbeda untuk bagian yang sama, sebutkan kedua aturan tersebut secara netral beserta rujukan halamannya.\n7. Bila informasi yang ditanyakan benar-benar TIDAK ADA di dalam Konteks Dokumen, Anda WAJIB menjawab dengan sopan: \"Maaf, informasi mengenai hal tersebut tidak ditemukan di dalam dokumen SOP yang tersedia. Silakan hubungi petugas layanan Diskominfotik Kota Banda Aceh untuk bantuan lebih lanjut.\" JANGAN pernah mengarang informasi yang tidak ada.\n8. Awali jawaban Anda dengan kalimat pengantar yang relevan dan akhiri dengan penawaran bantuan jika diperlukan.";
    }

    /**
     * Get Chatbot & RAG Prompt Settings
     */
    public function getChatbotSettings()
    {
        return response()->json([
            'llm_model_name' => AppSetting::getVal('llm_model_name', 'qwen2.5:3b'),
            'chatbot_name' => AppSetting::getVal('chatbot_name', 'Asisten Virtual Diskominfotik'),
            'chatbot_persona' => AppSetting::getVal('chatbot_persona', 'Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh'),
            'rag_system_prompt' => AppSetting::getVal('rag_system_prompt', self::getDefaultRagPrompt()),
            'rag_temperature' => (float) AppSetting::getVal('rag_temperature', '0.2'),
            'rag_top_k' => (int) AppSetting::getVal('rag_top_k', '8'),
            'rag_num_ctx' => (int) AppSetting::getVal('rag_num_ctx', '6144'),
            'chatbot_greeting' => AppSetting::getVal('chatbot_greeting', 'Halo! Saya asisten virtual resmi Diskominfotik Kota Banda Aceh. Ada yang bisa saya bantu terkait informasi SOP atau layanan kami?'),
            'chatbot_fallback_message' => AppSetting::getVal('chatbot_fallback_message', 'Maaf, informasi tersebut tidak ditemukan di dalam dokumen SOP yang tersedia. Silakan hubungi petugas Diskominfotik Kota Banda Aceh untuk informasi lebih lanjut.'),
            'rag_citation_enabled' => AppSetting::getVal('rag_citation_enabled', 'true') === 'true',
            'default_rag_prompt' => self::getDefaultRagPrompt(),
        ]);
    }

    /**
     * Update Chatbot & RAG Prompt Settings
     */
    public function updateChatbotSettings(Request $request)
    {
        $validated = $request->validate([
            'llm_model_name' => 'nullable|string|max:100',
            'chatbot_name' => 'required|string|max:100',
            'chatbot_persona' => 'required|string|max:255',
            'rag_system_prompt' => 'required|string',
            'rag_temperature' => 'required|numeric|min:0|max:1',
            'rag_top_k' => 'required|integer|min:1|max:30',
            'rag_num_ctx' => 'nullable|integer|min:1024|max:65536',
            'chatbot_greeting' => 'nullable|string|max:500',
            'chatbot_fallback_message' => 'nullable|string|max:500',
            'rag_citation_enabled' => 'required|boolean',
        ]);

        if (isset($validated['llm_model_name']) && !empty(trim($validated['llm_model_name']))) {
            AppSetting::setVal('llm_model_name', trim($validated['llm_model_name']));
        }
        AppSetting::setVal('chatbot_name', $validated['chatbot_name']);
        AppSetting::setVal('chatbot_persona', $validated['chatbot_persona']);
        AppSetting::setVal('rag_system_prompt', $validated['rag_system_prompt']);
        AppSetting::setVal('rag_temperature', (string) $validated['rag_temperature']);
        AppSetting::setVal('rag_top_k', (string) $validated['rag_top_k']);
        if (isset($validated['rag_num_ctx'])) {
            AppSetting::setVal('rag_num_ctx', (string) $validated['rag_num_ctx']);
        }
        AppSetting::setVal('chatbot_greeting', $validated['chatbot_greeting'] ?? '');
        AppSetting::setVal('chatbot_fallback_message', $validated['chatbot_fallback_message'] ?? '');
        AppSetting::setVal('rag_citation_enabled', $validated['rag_citation_enabled'] ? 'true' : 'false');

        return response()->json([
            'message' => 'Pengaturan Chatbot & Prompt RAG berhasil disimpan.',
            'settings' => $this->getChatbotSettings()->getData()
        ]);
    }

    /**
     * Reset Chatbot & RAG Prompt Settings to Factory Defaults
     */
    public function resetChatbotSettings()
    {
        AppSetting::setVal('llm_model_name', 'qwen2.5:3b');
        AppSetting::setVal('chatbot_name', 'Asisten Virtual Diskominfotik');
        AppSetting::setVal('chatbot_persona', 'Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh');
        AppSetting::setVal('rag_system_prompt', self::getDefaultRagPrompt());
        AppSetting::setVal('rag_temperature', '0.2');
        AppSetting::setVal('rag_top_k', '8');
        AppSetting::setVal('rag_num_ctx', '6144');
        AppSetting::setVal('chatbot_greeting', 'Halo! Saya asisten virtual resmi Diskominfotik Kota Banda Aceh. Ada yang bisa saya bantu terkait informasi SOP atau layanan kami?');
        AppSetting::setVal('chatbot_fallback_message', 'Maaf, informasi tersebut tidak ditemukan di dalam dokumen SOP yang tersedia. Silakan hubungi petugas Diskominfotik Kota Banda Aceh untuk informasi lebih lanjut.');
        AppSetting::setVal('rag_citation_enabled', 'true');

        return response()->json([
            'message' => 'Pengaturan Chatbot berhasil dikembalikan ke standar awal.',
            'settings' => $this->getChatbotSettings()->getData()
        ]);
    }

    /**
     * Resolve effective Ollama URL, ensuring Docker container translates localhost to host.docker.internal
     */
    private function resolveOllamaUrl(): string
    {
        $ollamaUrl = env('OLLAMA_BASE_URL', env('OLLAMA_URL', config('services.ai.ollama_url', 'http://host.docker.internal:11434')));
        if (str_contains($ollamaUrl, 'localhost') || str_contains($ollamaUrl, '127.0.0.1')) {
            $ollamaUrl = str_replace(['localhost', '127.0.0.1'], 'host.docker.internal', $ollamaUrl);
        }
        return rtrim($ollamaUrl, '/');
    }

    /**
     * Get list of all installed LLM models from Ollama with capacity recommendations
     */
    public function getAvailableModels()
    {
        $ollamaUrl = $this->resolveOllamaUrl();
        $models = [];
        $activeModel = AppSetting::getVal('llm_model_name', 'qwen2.5:3b');

        try {
            $response = \Illuminate\Support\Facades\Http::timeout(4)->get("{$ollamaUrl}/api/tags");
            if ($response->successful() && isset($response->json()['models'])) {
                $rawModels = $response->json()['models'];
                foreach ($rawModels as $m) {
                    $name = $m['name'] ?? '';
                    if (empty($name)) continue;

                    $sizeBytes = $m['size'] ?? 0;
                    $sizeGb = round($sizeBytes / (1024 * 1024 * 1024), 2);
                    $nameLower = strtolower($name);

                    // Skip vision-only or embedding models if clearly marked
                    $isVision = str_contains($nameLower, 'vl') || str_contains($nameLower, 'vision');
                    $isEmbedding = str_contains($nameLower, 'bge') || str_contains($nameLower, 'embed');

                    // Classification & recommendation based on parameter size
                    $tier = 'medium';
                    $badge = 'Sedang (Kualitas Tinggi, 1–2 User)';
                    $speed = '15–25 tok/s';
                    $vramEst = '~4.5–5.5 GB';
                    $tagColor = 'amber';

                    if (str_contains($nameLower, '0.5b') || str_contains($nameLower, '1.5b') || str_contains($nameLower, '1b') || str_contains($nameLower, '3b') || str_contains($nameLower, '2b')) {
                        $tier = 'light';
                        $badge = 'Sangat Ringan (Rekomendasi 3–5 User Bersamaan)';
                        $speed = '45–60 tok/s';
                        $vramEst = '~2.0–2.5 GB';
                        $tagColor = 'emerald';
                    } elseif (str_contains($nameLower, '14b') || str_contains($nameLower, '32b') || str_contains($nameLower, '70b') || $sizeGb > 9.0) {
                        $tier = 'heavy';
                        $badge = 'Sangat Berat (Butuh Server Khusus / GPU Besar)';
                        $speed = '3–8 tok/s';
                        $vramEst = '>10 GB';
                        $tagColor = 'rose';
                    } elseif ($isVision) {
                        $tier = 'specialized';
                        $badge = 'Model Vision (OCR / Dokumen Gambar)';
                        $speed = '10–20 tok/s';
                        $vramEst = '~6.0 GB';
                        $tagColor = 'indigo';
                    }

                    $models[] = [
                        'name' => $name,
                        'size_gb' => $sizeGb,
                        'tier' => $tier,
                        'badge' => $badge,
                        'speed' => $speed,
                        'vram_estimate' => $vramEst,
                        'tag_color' => $tagColor,
                        'is_active' => $name === $activeModel,
                        'is_vision' => $isVision,
                        'is_embedding' => $isEmbedding,
                    ];
                }
            }
        } catch (\Exception $e) {
            // Ollama offline or error
        }

        // Fallback default list if Ollama is offline or returned empty
        if (empty($models)) {
            $models = [
                [
                    'name' => 'qwen2.5:3b',
                    'size_gb' => 1.9,
                    'tier' => 'light',
                    'badge' => 'Sangat Ringan (Rekomendasi 3–5 User Bersamaan)',
                    'speed' => '45–60 tok/s',
                    'vram_estimate' => '~2.0–2.5 GB',
                    'tag_color' => 'emerald',
                    'is_active' => 'qwen2.5:3b' === $activeModel,
                    'is_vision' => false,
                    'is_embedding' => false,
                ],
                [
                    'name' => 'qwen3:8b',
                    'size_gb' => 5.2,
                    'tier' => 'medium',
                    'badge' => 'Sedang (Kualitas Tinggi, 1–2 User)',
                    'speed' => '15–25 tok/s',
                    'vram_estimate' => '~5.5 GB',
                    'tag_color' => 'amber',
                    'is_active' => 'qwen3:8b' === $activeModel,
                    'is_vision' => false,
                    'is_embedding' => false,
                ],
            ];
        }

        return response()->json([
            'active_model' => $activeModel,
            'models' => $models,
        ]);
    }

    /**
     * GET /api/settings/hardware — Real-time GPU VRAM, System RAM & Environment Diagnostics
     */
    public function getHardwareStatus(Request $request)
    {
        $aiUrl = config('services.ai.url', 'http://localhost:8080');
        $token = (string) config('services.ai_microservice.token');
        $model = $request->query('model');

        try {
            $response = \Illuminate\Support\Facades\Http::withHeaders([
                'Authorization' => "Bearer {$token}",
            ])->timeout(5)->get("{$aiUrl}/api/health/mesin", [
                'nocache' => 1,
                'model' => $model,
            ]);

            if ($response->successful()) {
                return response()->json([
                    'success' => true,
                    'data' => $response->json(),
                ]);
            }
        } catch (\Exception $e) {
            // AI service unavailable
        }

        return response()->json([
            'success' => false,
            'message' => 'Layanan Python AI tidak dapat dihubungi untuk membaca diagnostik hardware.',
        ], 503);
    }

    /**
     * POST /api/settings/models/benchmark — Test live inference speed (tok/s) on selected model
     */
    public function benchmarkModel(Request $request)
    {
        $request->validate([
            'model' => 'nullable|string|max:100',
        ]);

        $ollamaUrl = $this->resolveOllamaUrl();
        $model = $request->input('model') ?: AppSetting::getVal('llm_model_name', 'qwen2.5:3b');

        try {
            $startTime = microtime(true);
            $response = \Illuminate\Support\Facades\Http::timeout(60)->post("{$ollamaUrl}/api/generate", [
                'model' => $model,
                'prompt' => 'Sebutkan 3 prinsip utama pelayanan informasi publik bagi aparatur sipil negara dalam 2 kalimat singkat.',
                'stream' => false,
                'options' => [
                    'temperature' => 0.1,
                    'num_predict' => 40,
                ],
            ]);

            if (!$response->successful()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ollama gagal mengeksekusi inferensi benchmark: ' . ($response->json('error') ?? $response->body()),
                ], 500);
            }

            $data = $response->json();
            $evalCount = $data['eval_count'] ?? 0;
            $evalDurationNs = $data['eval_duration'] ?? 1;
            $promptEvalDurationNs = $data['prompt_eval_duration'] ?? 0;
            $totalDurationNs = $data['total_duration'] ?? 1;

            $tokPerSec = $evalDurationNs > 0 ? round($evalCount / ($evalDurationNs / 1e9), 1) : 0;
            $ttftMs = round($promptEvalDurationNs / 1e6);
            $totalDurationMs = round((microtime(true) - $startTime) * 1000);

            return response()->json([
                'success' => true,
                'model' => $model,
                'tokens_per_second' => $tokPerSec,
                'eval_count' => $evalCount,
                'eval_duration_ms' => round($evalDurationNs / 1e6),
                'time_to_first_token_ms' => $ttftMs,
                'total_duration_ms' => $totalDurationMs,
                'sample_output' => trim($data['response'] ?? ''),
                'tested_at' => now()->translatedFormat('H:i:s, d M Y'),
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal menjalankan benchmark: ' . $e->getMessage(),
            ], 500);
        }
    }
}
