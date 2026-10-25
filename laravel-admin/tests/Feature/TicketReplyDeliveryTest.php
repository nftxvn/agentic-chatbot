<?php

namespace Tests\Feature;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Jobs\DeliverTicketWebhook;
use App\Models\ApiKey;
use App\Models\AppSetting;
use App\Models\ChatTicket;
use App\Models\User;
use App\Models\WebhookDelivery;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class TicketReplyDeliveryTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        Event::fake([TicketMessageSent::class, TicketUpdated::class]);
        Queue::fake([DeliverTicketWebhook::class]);
        Http::preventStrayRequests();
        Http::fake(['https://api.telegram.org/*' => Http::response(['ok' => true])]);
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('test-delivery-token'));
        $this->actingAs(User::factory()->create());
    }

    public function test_public_reply_sends_to_channel_and_queues_api_webhook(): void
    {
        $ticket = $this->telegramTicket();

        $response = $this->postJson("/api/tickets/{$ticket->id}/messages", [
            'message' => 'Balasan petugas untuk warga',
        ])->assertCreated();

        Http::assertSent(function (Request $request) {
            return $request->url() === 'https://api.telegram.org/bottest-delivery-token/sendMessage'
                && $request['chat_id'] === '12345'
                && $request['text'] === 'Balasan petugas untuk warga';
        });
        Http::assertSentCount(1);

        $delivery = WebhookDelivery::sole();
        $this->assertSame($ticket->id, $delivery->ticket_id);
        $this->assertSame($response->json('data.id'), $delivery->ticket_message_id);
        $this->assertSame('ticket.reply.created', $delivery->event_type);
        $this->assertSame('queued', $delivery->status);
        Queue::assertPushed(DeliverTicketWebhook::class, function ($job) use ($delivery) {
            return $job->deliveryId === $delivery->id;
        });
        Queue::assertPushed(DeliverTicketWebhook::class, 1);
    }

    public function test_internal_note_is_saved_without_external_delivery(): void
    {
        $ticket = $this->telegramTicket();

        $this->postJson("/api/tickets/{$ticket->id}/messages", [
            'message' => 'Catatan untuk petugas saja',
            'is_internal_note' => true,
        ])->assertCreated()->assertJsonPath('data.is_internal_note', true);

        Http::assertNothingSent();
        Queue::assertNothingPushed();
        $this->assertDatabaseCount('webhook_deliveries', 0);
        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticket->id,
            'message' => 'Catatan untuk petugas saja',
            'is_internal_note' => true,
        ]);
        $this->assertSame('open', $ticket->fresh()->status);
        $this->assertNull($ticket->fresh()->assigned_admin_id);
    }

    public function test_disabled_webhook_keeps_channel_reply_working(): void
    {
        $ticket = $this->telegramTicket();
        ApiKey::findOrFail($ticket->api_key_id)->update(['webhook_enabled' => false]);

        $this->postJson("/api/tickets/{$ticket->id}/messages", [
            'message' => 'Balasan melalui kanal tetap terkirim',
        ])->assertCreated();

        Http::assertSentCount(1);
        Queue::assertNothingPushed();
        $this->assertDatabaseCount('webhook_deliveries', 0);
    }

    #[DataProvider('whatsappGateways')]
    public function test_whatsapp_reply_preserves_gateway_payload(
        string $url,
        string $authorization,
        array $expectedPayload,
    ): void {
        AppSetting::setVal('wa_api_url', $url);
        AppSetting::setVal('wa_token', Crypt::encryptString('test-wa-token'));
        Http::fake([$url => Http::response(['ok' => true])]);
        $ticket = ChatTicket::create([
            'session_id' => 'wa-628123456789',
            'citizen_contact' => '+62 812-3456-789',
            'channel' => 'whatsapp',
            'status' => 'open',
        ]);

        $this->postJson("/api/tickets/{$ticket->id}/messages", [
            'message' => 'Balasan WhatsApp',
        ])->assertCreated();

        Http::assertSent(function (Request $request) use ($url, $authorization, $expectedPayload) {
            return $request->url() === $url
                && $request->hasHeader('Authorization', $authorization)
                && $request->data() === $expectedPayload;
        });
        Http::assertSentCount(1);
        Queue::assertNothingPushed();
    }

    public static function whatsappGateways(): array
    {
        return [
            'generic gateway' => [
                'https://wa-gateway.example.test/send',
                'test-wa-token',
                [
                    'target' => '+62 812-3456-789',
                    'phone' => '+62 812-3456-789',
                    'message' => 'Balasan WhatsApp',
                ],
            ],
            'Meta Cloud API' => [
                'https://graph.facebook.com/test/messages',
                'Bearer test-wa-token',
                [
                    'messaging_product' => 'whatsapp',
                    'recipient_type' => 'individual',
                    'to' => '628123456789',
                    'type' => 'text',
                    'text' => ['preview_url' => false, 'body' => 'Balasan WhatsApp'],
                ],
            ],
        ];
    }

    private function telegramTicket(): ChatTicket
    {
        $apiKey = ApiKey::create([
            'name' => 'Delivery test',
            'key' => 'sk_live_delivery_test',
            'is_active' => true,
            'webhook_url' => 'https://receiver.example.test/ticket-replies',
            'webhook_secret' => 'test-webhook-secret',
            'webhook_enabled' => true,
        ]);

        return ChatTicket::create([
            'session_id' => 'telegram-12345',
            'api_key_id' => $apiKey->id,
            'channel' => 'telegram',
            'status' => 'open',
        ]);
    }
}
