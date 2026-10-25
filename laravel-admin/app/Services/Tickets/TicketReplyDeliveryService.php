<?php

namespace App\Services\Tickets;

use App\Jobs\DeliverTicketWebhook;
use App\Models\ApiKey;
use App\Models\AppSetting;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use App\Models\WebhookDelivery;
use App\Services\AttachmentService;
use App\Services\WhatsAppClient;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

class TicketReplyDeliveryService
{
    public function __construct(private WhatsAppClient $whatsapp)
    {
    }

    /**
     * Deliver public agent replies through their channel and API webhook.
     */
    public function deliver(ChatTicket $ticket, ChatTicketMessage $message): void
    {
        if ($message->is_internal_note) {
            return;
        }

        $this->dispatchOutboundMessage($ticket, $message->message, $message->attachments ?? []);
        $this->queueApiWebhook($ticket, $message);
    }

    /**
     * Dispatch agent reply to external channels (Telegram, WhatsApp).
     */
    private function dispatchOutboundMessage(ChatTicket $ticket, string $replyText, array $attachments = []): void
    {
        $channel = strtolower($ticket->channel ?? 'web');
        $contact = $ticket->citizen_contact;
        $sessionId = $ticket->session_id;

        // 1. Channel: Telegram
        if ($channel === 'telegram' || str_starts_with($sessionId, 'telegram-')) {
            $chatId = $contact ?: str_replace('telegram-', '', $sessionId);
            if (!empty($chatId)) {
                $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
                if (!empty($encryptedToken)) {
                    try {
                        $token = Crypt::decryptString($encryptedToken);

                        // If has image attachment, send photo natively
                        $hasPhoto = false;
                        foreach ($attachments as $att) {
                            if (!empty($att['file_path']) && str_starts_with($att['mime_type'] ?? '', 'image/')) {
                                $caption = ($replyText !== '[Lampiran Berkas]' && $replyText !== '[Lampiran Foto]') ? $replyText : null;
                                AttachmentService::sendPhotoToTelegram($token, $chatId, $att['file_path'], $caption);
                                $hasPhoto = true;
                                break;
                            }
                        }

                        // Send text message if no photo sent with caption
                        if (!$hasPhoto) {
                            Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                                'chat_id' => $chatId,
                                'text' => $replyText,
                            ]);
                        }
                        Log::info("Balasan admin berhasil dikirim ke Telegram ({$chatId}).");
                    } catch (\Exception $e) {
                        Log::error("Gagal mengirim balasan admin ke Telegram: " . $e->getMessage());
                    }
                }
            }
        }

        // 2. Channel: WhatsApp
        if ($channel === 'whatsapp' || str_starts_with($sessionId, 'wa-') || str_starts_with($sessionId, 'whatsapp-')) {
            $phone = $contact ?: preg_replace('/[^0-9]/', '', $sessionId);
            if (!empty($phone)) {
                try {
                    $this->whatsapp->send($phone, $replyText);
                    Log::info("Balasan admin berhasil dikirim ke WhatsApp ({$phone}).");
                } catch (\Exception $e) {
                    Log::error("Gagal mengirim balasan admin ke WhatsApp: " . $e->getMessage());
                }
            }
        }
    }

    private function queueApiWebhook(ChatTicket $ticket, ChatTicketMessage $message): void
    {
        if (!$ticket->api_key_id || $message->is_internal_note) {
            return;
        }

        $apiKey = ApiKey::find($ticket->api_key_id);
        if (!$apiKey || !$apiKey->is_active || !$apiKey->webhook_enabled || !$apiKey->webhook_url || !$apiKey->webhook_secret) {
            return;
        }

        $delivery = WebhookDelivery::create([
            'event_id' => (string) Str::uuid(),
            'api_key_id' => $apiKey->id,
            'ticket_id' => $ticket->id,
            'ticket_message_id' => $message->id,
            'event_type' => 'ticket.reply.created',
            'status' => 'queued',
        ]);

        try {
            DeliverTicketWebhook::dispatch($delivery->id);
        } catch (\Throwable $exception) {
            $delivery->update([
                'status' => 'failed',
                'last_error' => mb_substr($exception->getMessage(), 0, 2000),
            ]);

            Log::warning('Gagal memasukkan webhook balasan tiket ke antrean.', [
                'delivery_id' => $delivery->id,
                'error' => $exception->getMessage(),
            ]);
        }
    }
}
