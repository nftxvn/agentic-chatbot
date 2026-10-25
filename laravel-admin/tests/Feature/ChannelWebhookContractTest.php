<?php

namespace Tests\Feature;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Http\Controllers\Api\V1\TelegramWebhookController;
use App\Models\AppSetting;
use App\Models\ChatLog;
use App\Models\ChatTicket;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Redis;
use Tests\TestCase;

class ChannelWebhookContractTest extends TestCase
{
    use RefreshDatabase;

    private RecordingTelegramWebhookController $telegram;
    private int $aiStatus = 200;
    private int $gatewayStatus = 200;
    private array $aiReply = ['reply' => 'Jawaban layanan', 'sources' => [['doc_name' => 'Panduan', 'document_id' => 1, 'page' => 2]]];

    protected function setUp(): void
    {
        parent::setUp();
        config(['cache.default' => 'array', 'services.ai.url' => 'http://ai.example.test', 'services.ai_microservice.token' => 'test-internal-token']);
        Cache::flush();
        Event::fake([TicketMessageSent::class, TicketUpdated::class]);
        Http::preventStrayRequests();
        Http::fake([
            'http://ai.example.test/api/chat/message' => fn () => Http::response($this->aiReply, $this->aiStatus),
            'https://gateway.example.test/send' => fn () => Http::response(['status' => true], $this->gatewayStatus),
        ]);
        $this->telegram = $this->app->make(RecordingTelegramWebhookController::class);
        $this->app->instance(TelegramWebhookController::class, $this->telegram);
    }

    private function activateWhatsapp(): void
    {
        AppSetting::setVal('wa_status', 'true');
        AppSetting::setVal('wa_api_url', 'https://gateway.example.test/send');
        AppSetting::setVal('wa_token', Crypt::encryptString('synthetic-wa-token'));
    }

    private function activateTelegram(): void
    {
        AppSetting::setVal('telegram_status', 'true');
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('synthetic-telegram-token'));
    }

    private function telegramUpdate(int $update = 1, int $message = 5): array
    {
        return ['update_id' => $update, 'message' => [
            'message_id' => $message, 'chat' => ['id' => 123],
            'from' => ['first_name' => 'Naufal', 'username' => 'naufal'], 'text' => 'Informasi layanan',
        ]];
    }

    public function test_whatsapp_disabled_and_non_text_payload_are_ignored(): void
    {
        $this->postJson('/api/v1/webhook/whatsapp', ['sender' => '62812', 'message' => 'Halo'])
            ->assertOk()->assertExactJson(['status' => 'ignored', 'reason' => 'whatsapp_disabled']);
        $this->activateWhatsapp();
        $this->postJson('/api/v1/webhook/whatsapp', [])->assertOk()
            ->assertExactJson(['status' => 'ignored', 'reason' => 'no_text_or_sender']);
        Http::assertNothingSent();
    }

    public function test_whatsapp_verification_preserves_challenge_and_forbidden_response(): void
    {
        AppSetting::setVal('wa_webhook_verify_token', 'synthetic-verify');
        $this->get('/api/v1/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=synthetic-verify&hub.challenge=12345')
            ->assertOk()->assertSee('12345');
        $this->get('/api/v1/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=wrong')->assertForbidden();
    }

    public function test_webhook_file_field_does_not_replace_text_input(): void
    {
        $this->activateWhatsapp();
        $this->post('/api/v1/webhook/whatsapp', [
            'sender' => '62812', 'message' => UploadedFile::fake()->create('message.bin', 1),
        ])->assertOk()->assertExactJson(['status' => 'ignored', 'reason' => 'no_text_or_sender']);
        Http::assertNothingSent();
    }

    public function test_whatsapp_generic_payload_normalizes_session_but_keeps_phone_and_citations(): void
    {
        $this->activateWhatsapp();
        $this->postJson('/api/v1/webhook/whatsapp', ['sender' => '+62 812-34', 'message' => 'Halo'])
            ->assertOk()->assertExactJson(['status' => 'success', 'session_id' => 'wa-6281234', 'recipient' => '+62 812-34']);
        Http::assertSent(fn ($r) => $r->url() === 'http://ai.example.test/api/chat/message'
            && $r['phone_number'] === '+62 812-34' && $r['session_id'] === 'wa-6281234'
            && $r['message'] === 'Halo' && $r->hasHeader('Authorization', 'Bearer test-internal-token'));
        Http::assertSent(fn ($r) => $r->url() === 'https://gateway.example.test/send'
            && $r['message'] === "Jawaban layanan\n\n*Rujukan Dokumen SOP:*\n• Panduan (Hal. 2)");
        $log = ChatLog::sole();
        $this->assertNull($log->query);
        $this->assertNull($log->answer);
        $this->assertSame('Pengguna WhatsApp', $log->sender_identifier);
        $this->assertEquals(['count' => 1], $log->sources_json);
    }

    public function test_meta_text_takes_precedence_over_generic_fields(): void
    {
        $this->activateWhatsapp();
        $this->postJson('/api/v1/webhook/whatsapp', [
            'entry' => [['changes' => [['value' => ['messages' => [['from' => '62899', 'text' => ['body' => 'Meta text']]]]]]]],
            'sender' => 'other', 'message' => 'Generic text',
        ])->assertOk()->assertJsonPath('recipient', '62899');
        Http::assertSent(fn ($r) => $r->url() === 'http://ai.example.test/api/chat/message' && $r['message'] === 'Meta text');
    }

    public function test_whatsapp_active_ticket_bypasses_ai_and_emits_existing_events(): void
    {
        $this->activateWhatsapp();
        $ticket = ChatTicket::create(['session_id' => 'wa-62812', 'status' => 'in_progress', 'channel' => 'whatsapp', 'citizen_name' => 'Naufal']);
        $this->postJson('/api/v1/webhook/whatsapp', ['phone' => '62812', 'text' => 'Tambahan berkas'])
            ->assertOk()->assertExactJson(['status' => 'forwarded_to_live_chat', 'ticket_id' => $ticket->id]);
        $this->assertSame('Tambahan berkas', $ticket->messages()->sole()->message);
        $this->assertSame('62812', $ticket->fresh()->citizen_contact);
        Event::assertDispatched(TicketMessageSent::class);
        Event::assertDispatched(TicketUpdated::class);
        Http::assertNothingSent();
    }

    public function test_whatsapp_ai_failure_does_not_send_gateway_message(): void
    {
        $this->activateWhatsapp();
        $this->aiStatus = 503;
        $this->postJson('/api/v1/webhook/whatsapp', ['from' => '62812', 'body' => 'Halo'])
            ->assertStatus(500)->assertExactJson(['status' => 'error', 'message' => 'AI processing failed']);
        Http::assertSentCount(1);
        $this->assertSame(0, ChatLog::count());
    }

    public function test_whatsapp_gateway_rejection_keeps_existing_success_response(): void
    {
        $this->activateWhatsapp();
        $this->aiReply = ['reply' => 'Jawaban', 'sources' => []];
        $this->gatewayStatus = 502;
        $this->postJson('/api/v1/webhook/whatsapp', ['sender' => '62812', 'message' => 'Halo'])
            ->assertOk()->assertJsonPath('status', 'success');
        $this->assertSame(1, ChatLog::count());
    }

    public function test_whatsapp_citations_can_be_disabled(): void
    {
        $this->activateWhatsapp();
        AppSetting::setVal('rag_citation_enabled', 'false');
        $this->postJson('/api/v1/webhook/whatsapp', ['sender' => '62812', 'message' => 'Halo'])->assertOk();
        Http::assertSent(fn ($r) => $r->url() === 'https://gateway.example.test/send' && $r['message'] === 'Jawaban layanan');
    }

    public function test_telegram_disabled_update_is_ignored_without_locks_or_network(): void
    {
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate())->assertOk()
            ->assertExactJson(['status' => 'ignored', 'reason' => 'telegram_disabled']);
        $this->assertFalse(Cache::has('telegram:update:1'));
        Http::assertNothingSent();
    }

    public function test_telegram_duplicate_update_and_message_ids_are_independent(): void
    {
        $this->activateTelegram();
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate())->assertOk()->assertJsonPath('status', 'success');
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate())->assertOk()->assertJsonPath('reason', 'duplicate_update_id');
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate(2))->assertOk()->assertJsonPath('reason', 'duplicate_message_id');
        $this->assertCount(1, $this->telegram->calls);
    }

    public function test_telegram_invalid_payload_still_consumes_update_lock(): void
    {
        $this->activateTelegram();
        $this->postJson('/api/v1/webhook/telegram', ['update_id' => 7])->assertOk()->assertJsonPath('reason', 'no_text_or_chat_id');
        $this->postJson('/api/v1/webhook/telegram', ['update_id' => 7])->assertOk()->assertJsonPath('reason', 'duplicate_update_id');
    }

    public function test_edited_telegram_message_keeps_existing_no_text_behavior(): void
    {
        $this->activateTelegram();
        $this->postJson('/api/v1/webhook/telegram', ['update_id' => 5, 'edited_message' => [
            'message_id' => 9, 'chat' => ['id' => 123], 'text' => 'Edited text',
        ]])->assertOk()->assertJsonPath('reason', 'no_text_or_chat_id');
        $this->assertCount(0, $this->telegram->calls);
    }

    public function test_telegram_missing_or_invalid_token_keeps_http_200_error(): void
    {
        AppSetting::setVal('telegram_status', 'true');
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate())->assertOk()->assertJsonPath('reason', 'missing_bot_token');
        AppSetting::setVal('telegram_bot_token', 'invalid-ciphertext');
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate(2, 6))->assertOk()->assertJsonPath('reason', 'decrypt_failed');
    }

    public function test_telegram_active_ticket_receives_text_without_ai(): void
    {
        $this->activateTelegram();
        $ticket = ChatTicket::create(['session_id' => 'telegram-123', 'status' => 'open', 'channel' => 'telegram', 'citizen_name' => 'Naufal']);
        $this->postJson('/api/v1/webhook/telegram', $this->telegramUpdate())->assertOk()
            ->assertExactJson(['status' => 'forwarded_to_live_chat', 'ticket_id' => $ticket->id]);
        $this->assertSame('Informasi layanan', $ticket->messages()->sole()->message);
        $this->assertSame('@naufal (ID: 123)', $ticket->fresh()->citizen_contact);
        $this->assertCount(0, $this->telegram->calls);
        Http::assertNothingSent();
    }

    public function test_telegram_reset_clears_existing_session_and_sends_greeting(): void
    {
        $this->activateTelegram();
        $connection = \Mockery::mock();
        $connection->shouldReceive('select')->once()->with(2);
        Redis::shouldReceive('connection')->once()->andReturn($connection);
        Redis::shouldReceive('del')->once()->with('chatbot:session:telegram-123');
        $update = $this->telegramUpdate();
        $update['message']['text'] = '/reset';
        $this->postJson('/api/v1/webhook/telegram', $update)->assertOk();
        $this->assertSame('Halo', $this->telegram->calls[0]['text']);
    }
}

class RecordingTelegramWebhookController extends TelegramWebhookController
{
    public array $calls = [];

    protected function streamAiToTelegram(string $token, int|string $chatId, string $text, string $fromName = 'User', ?string $fromUsername = null): void
    {
        $this->calls[] = compact('chatId', 'text', 'fromName', 'fromUsername');
    }
}
