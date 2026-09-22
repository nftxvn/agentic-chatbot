<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Api\SettingController;
use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class WhatsAppWebhookController extends Controller
{
    /**
     * Get Python AI backend base URL
     */
    protected function getAiBaseUrl(): string
    {
        return config('services.ai.url', 'http://localhost:8080');
    }

    /**
     * Token untuk memanggil layanan Python AI.
     *
     * Lihat catatan yang sama di ChatController::getInternalToken() — kuncinya
     * `services.ai_microservice.token`, bukan `services.ai.internal_token` yang
     * tidak pernah ada dan diam-diam jatuh ke string default.
     */
    protected function getInternalToken(): string
    {
        return (string) config('services.ai_microservice.token');
    }

    /**
     * GET /api/v1/webhook/whatsapp — Verifikasi Webhook Meta WhatsApp Cloud API
     */
    public function verify(Request $request)
    {
        $mode = $request->query('hub_mode', $request->query('hub.mode'));
        $token = $request->query('hub_verify_token', $request->query('hub.verify_token'));
        $challenge = $request->query('hub_challenge', $request->query('hub.challenge'));

        $expectedToken = AppSetting::getVal('wa_webhook_verify_token', 'diskominfo_wa_rag_token');

        if ($mode === 'subscribe' && $token === $expectedToken) {
            Log::info('Meta WhatsApp Webhook Terverifikasi');
            return response($challenge, 200)->header('Content-Type', 'text/plain');
        }

        Log::warning('Meta WhatsApp Webhook Verifikasi Gagal', [
            'mode' => $mode,
            'received_token' => $token,
        ]);

        return response()->json(['message' => 'Verifikasi token tidak cocok.'], 403);
    }

    /**
     * POST /api/v1/webhook/whatsapp — Handle Inbound WhatsApp Messages
     */
    public function handle(Request $request)
    {
        // 1. Cek apakah layanan WhatsApp aktif
        $isActive = AppSetting::getVal('wa_status', 'false') === 'true';
        if (!$isActive) {
            Log::info('Pesan WhatsApp diabaikan karena status WhatsApp chatbot sedang nonaktif.');
            return response()->json(['status' => 'ignored', 'reason' => 'whatsapp_disabled']);
        }

        // 2. Ekstraksi nomor pengirim dan isi pesan dari berbagai format gateway
        $from = null;
        $messageText = null;

        // A. Format Meta WhatsApp Cloud API
        $metaMessages = $request->input('entry.0.changes.0.value.messages');
        if (is_array($metaMessages) && !empty($metaMessages)) {
            $firstMsg = $metaMessages[0];
            $from = $firstMsg['from'] ?? null;
            $messageText = $firstMsg['text']['body'] ?? null;
        }

        // B. Format Generic / Fonnte / Wablas / Custom Gateway
        if (!$messageText) {
            $from = $request->input('sender') ?? $request->input('phone') ?? $request->input('from') ?? $from;
            $messageText = $request->input('message') ?? $request->input('text') ?? $request->input('body');
        }

        if (empty($from) || empty($messageText)) {
            return response()->json(['status' => 'ignored', 'reason' => 'no_text_or_sender']);
        }

        Log::info('Pesan WhatsApp Masuk', [
            'from' => $from,
            'message' => substr($messageText, 0, 80),
        ]);

        // 3. Panggil RAG Engine di Python AI
        $systemPrompt = AppSetting::getVal('rag_system_prompt', SettingController::getDefaultRagPrompt());
        $temperature = (float) AppSetting::getVal('rag_temperature', '0.2');
        $topK = (int) AppSetting::getVal('rag_top_k', '8');
        $citationEnabled = AppSetting::getVal('rag_citation_enabled', 'true') === 'true';

        $sessionId = 'wa-' . preg_replace('/[^0-9]/', '', $from);

        try {
            $response = Http::withHeaders([
                'Authorization' => 'Bearer ' . $this->getInternalToken(),
                'Content-Type' => 'application/json',
            ])->timeout(60)->post($this->getAiBaseUrl() . '/api/chat/message', [
                'message' => $messageText,
                'phone_number' => $from,
                'session_id' => $sessionId,
                'system_prompt' => $systemPrompt,
                'temperature' => $temperature,
                'top_k' => $topK,
            ]);

            if (!$response->successful()) {
                Log::error('RAG Engine gagal memproses pesan WhatsApp', [
                    'status' => $response->status(),
                    'body' => $response->body(),
                ]);
                return response()->json(['status' => 'error', 'message' => 'AI processing failed'], 500);
            }

            $aiData = $response->json();
            $replyText = $aiData['reply'] ?? '';
            $sources = $aiData['sources'] ?? [];

            // 4. Format jawaban untuk WhatsApp (teks rapi dengan rujukan)
            $formattedReply = $replyText;

            if ($citationEnabled && !empty($sources) && !str_contains($replyText, 'Rujukan:')) {
                $formattedReply .= "\n\n*Rujukan Dokumen SOP:*";
                foreach ($sources as $source) {
                    $docName = $source['doc_name'] ?? ('Dokumen #' . $source['document_id']);
                    $pageStr = !empty($source['page']) ? " (Hal. {$source['page']})" : '';
                    $formattedReply .= "\n• {$docName}{$pageStr}";
                }
            }

            // 5. Kirim balasan ke WhatsApp Gateway jika API URL & Token terpasang
            $this->sendWhatsAppMessage($from, $formattedReply);

            // 6. Catat telemetri interaksi WhatsApp (Privasi warga terlindungi: tanpa nomor HP dan tanpa isi pesan)
            $isFallback = empty($sources) || str_contains($replyText, 'tidak ditemukan');
            \App\Models\ChatLog::create([
                'session_id' => $sessionId,
                'channel' => 'whatsapp',
                'api_key_id' => null,
                'sender_identifier' => 'Pengguna WhatsApp',
                'query' => null,
                'answer' => null,
                'sources_json' => !empty($sources) ? ['count' => count($sources)] : null,
                'is_fallback' => $isFallback,
                'response_time_ms' => null,
            ]);

            return response()->json([
                'status' => 'success',
                'session_id' => $sessionId,
                'recipient' => $from,
            ]);
        } catch (\Exception $e) {
            Log::error('Exception saat memproses webhook WhatsApp', ['error' => $e->getMessage()]);
            return response()->json(['status' => 'error', 'message' => $e->getMessage()], 500);
        }
    }

    /**
     * Kirim pesan keluar ke WhatsApp Gateway
     */
    public function sendWhatsAppMessage(string $to, string $message): bool
    {
        $apiUrl = AppSetting::getVal('wa_api_url', '');
        $encryptedToken = AppSetting::getVal('wa_token', '');

        if (empty($apiUrl) || empty($encryptedToken)) {
            Log::warning('Tidak dapat mengirim pesan WhatsApp: URL API atau Token belum dikonfigurasi.');
            return false;
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            Log::error('Gagal mendekripsi WhatsApp Token: ' . $e->getMessage());
            return false;
        }

        try {
            // Deteksi format payload berdasarkan tipe API Gateway
            if (str_contains($apiUrl, 'graph.facebook.com')) {
                // Meta Cloud API Format
                $payload = [
                    'messaging_product' => 'whatsapp',
                    'recipient_type' => 'individual',
                    'to' => preg_replace('/[^0-9]/', '', $to),
                    'type' => 'text',
                    'text' => ['preview_url' => false, 'body' => $message],
                ];

                $response = Http::withHeaders([
                    'Authorization' => 'Bearer ' . $token,
                    'Content-Type' => 'application/json',
                ])->timeout(15)->post($apiUrl, $payload);
            } else {
                // Generic Gateway (Fonnte / Wablas / Custom Gateway)
                $payload = [
                    'target' => $to,
                    'phone' => $to,
                    'message' => $message,
                ];

                $response = Http::withHeaders([
                    'Authorization' => $token,
                    'Content-Type' => 'application/json',
                ])->timeout(15)->post($apiUrl, $payload);
            }

            Log::info('Pesan WhatsApp terkirim ke gateway', [
                'recipient' => $to,
                'status' => $response->status(),
            ]);

            return $response->successful();
        } catch (\Exception $e) {
            Log::error('Gagal mengirim HTTP request ke WhatsApp Gateway: ' . $e->getMessage());
            return false;
        }
    }
}
