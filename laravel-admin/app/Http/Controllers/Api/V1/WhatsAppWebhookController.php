<?php

namespace App\Http\Controllers\Api\V1;

use App\Services\Channels\WhatsAppInboundHandler;
use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use App\Services\WhatsAppClient;
use Illuminate\Http\Request;
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
        $result = app(WhatsAppInboundHandler::class)->handle(
            $request->input(), $this->getAiBaseUrl(), $this->getInternalToken(),
            fn (string $to, string $message) => $this->sendWhatsAppMessage($to, $message),
        );

        return response()->json($result->payload, $result->status);
    }

    /**
     * Keep the public sender entrypoint used by webhook integrations.
     */
    public function sendWhatsAppMessage(string $to, string $message): bool
    {
        return app(WhatsAppClient::class)->send($to, $message);
    }
}
