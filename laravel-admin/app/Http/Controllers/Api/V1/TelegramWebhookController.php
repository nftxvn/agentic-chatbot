<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Services\Channels\TelegramInboundHandler;
use App\Services\Channels\TelegramAiResponder;
use Illuminate\Http\Request;

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
        $result = app(TelegramInboundHandler::class)->handle(
            $request->input(),
            fn ($token, $chatId, $text, $fromName, $fromUsername) => $this->streamAiToTelegram($token, $chatId, $text, $fromName, $fromUsername),
        );

        return response()->json($result->payload, $result->status);
    }

    /**
     * Memproses respon AI secara streaming dan memperbarui pesan di Telegram secara real-time.
     */
    protected function streamAiToTelegram(string $token, int|string $chatId, string $text, string $fromName = 'User', ?string $fromUsername = null): void
    {
        app(TelegramAiResponder::class)->replyToWebhook(
            $token, $chatId, $text, $this->getAiBaseUrl(), $this->getInternalToken(), $fromName, $fromUsername,
        );
    }
}
