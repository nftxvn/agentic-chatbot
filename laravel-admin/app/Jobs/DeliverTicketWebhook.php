<?php

namespace App\Jobs;

use App\Models\WebhookDelivery;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

class DeliverTicketWebhook implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 5;

    public int $timeout = 25;

    public function __construct(public int $deliveryId)
    {
    }

    /** @return array<int, int> */
    public function backoff(): array
    {
        return [15, 60, 300, 900];
    }

    public function handle(): void
    {
        $delivery = WebhookDelivery::with(['apiKey', 'ticket', 'ticketMessage'])->findOrFail($this->deliveryId);
        $apiKey = $delivery->apiKey;
        $ticket = $delivery->ticket;
        $message = $delivery->ticketMessage;

        if (!$apiKey || !$ticket || !$message || !$apiKey->is_active || !$apiKey->webhook_enabled || !$apiKey->webhook_url || !$apiKey->webhook_secret) {
            $delivery->update([
                'status' => 'failed',
                'attempts' => $this->attempts(),
                'last_error' => 'Webhook API key tidak aktif atau konfigurasinya tidak lengkap.',
            ]);
            return;
        }

        $payload = [
            'event' => $delivery->event_type,
            'event_id' => $delivery->event_id,
            'ticket' => [
                'id' => $ticket->id,
                'number' => $ticket->ticket_number,
                'session_id' => $ticket->session_id,
                'status' => $ticket->status,
                'channel' => $ticket->channel,
            ],
            'message' => [
                'id' => $message->id,
                'text' => $message->message,
                'sender' => $message->sender_name,
                'sent_at' => $message->created_at?->toISOString(),
                'attachments' => $message->attachments ?? [],
            ],
            'sent_at' => now()->toISOString(),
        ];

        $body = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        $timestamp = (string) now()->timestamp;
        $signature = hash_hmac('sha256', $timestamp . '.' . $body, $apiKey->webhook_secret);

        $delivery->update([
            'status' => 'sending',
            'attempts' => $this->attempts(),
            'last_error' => null,
        ]);

        try {
            $response = Http::timeout(15)
                ->withHeaders([
                    'X-SAPA-Event' => $delivery->event_type,
                    'X-SAPA-Delivery-Id' => $delivery->event_id,
                    'X-SAPA-Timestamp' => $timestamp,
                    'X-SAPA-Signature' => 'sha256=' . $signature,
                ])
                ->withBody($body, 'application/json')
                ->post($apiKey->webhook_url);

            $delivery->response_status = $response->status();

            if (!$response->successful()) {
                throw new \RuntimeException('Penerima webhook merespons HTTP ' . $response->status() . '.');
            }

            $delivery->update([
                'status' => 'delivered',
                'response_status' => $response->status(),
                'delivered_at' => now(),
                'last_error' => null,
            ]);
        } catch (Throwable $exception) {
            $delivery->update([
                'status' => 'queued',
                'response_status' => $delivery->response_status,
                'last_error' => mb_substr($exception->getMessage(), 0, 2000),
            ]);

            throw $exception;
        }
    }

    public function failed(Throwable $exception): void
    {
        WebhookDelivery::whereKey($this->deliveryId)->update([
            'status' => 'failed',
            'last_error' => mb_substr($exception->getMessage(), 0, 2000),
        ]);

        Log::warning('Pengiriman webhook tiket gagal setelah seluruh percobaan.', [
            'delivery_id' => $this->deliveryId,
            'error' => $exception->getMessage(),
        ]);
    }
}
