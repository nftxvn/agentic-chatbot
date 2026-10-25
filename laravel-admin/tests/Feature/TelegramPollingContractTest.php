<?php

namespace Tests\Feature;

use App\Events\TicketCreated;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\AppSetting;
use App\Models\ChatTicket;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class TelegramPollingContractTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);
        Http::preventStrayRequests();
    }

    private function fakeUpdates(array $updates): void
    {
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('poll-token'));
        AppSetting::setVal('telegram_status', 'true');
        Http::fake([
            '*getMe' => Http::response(['ok' => true, 'result' => ['first_name' => 'Test', 'username' => 'test_bot']]),
            '*deleteWebhook' => Http::response(['ok' => true]),
            '*getUpdates*' => Http::response(['ok' => true, 'result' => $updates]),
            '*getFile*' => Http::response(['ok' => false], 400),
            '*sendMessage' => Http::response(['ok' => true]),
        ]);
    }

    public function test_missing_token_exits_before_network(): void
    {
        $this->artisan('telegram:poll', ['--once' => true])->assertExitCode(1);
        Http::assertNothingSent();
    }

    public function test_once_polling_registers_bot_and_uses_existing_long_poll_options(): void
    {
        $this->fakeUpdates([]);
        $this->artisan('telegram:poll', ['--once' => true])->assertExitCode(0);
        $this->assertSame('@test_bot', AppSetting::getVal('telegram_bot_username'));
        Http::assertSent(fn ($r) => str_contains($r->url(), 'getUpdates') && $r['offset'] === 0 && $r['timeout'] === 20
            && $r['allowed_updates'] === '["message","edited_message"]');
    }

    public function test_polling_active_ticket_accepts_edited_messages_without_ai(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'telegram-123', 'status' => 'open', 'channel' => 'telegram', 'citizen_name' => 'Naufal']);
        $this->fakeUpdates([['update_id' => 8, 'edited_message' => [
            'message_id' => 9, 'chat' => ['id' => 123], 'from' => ['first_name' => 'Naufal'], 'text' => '  Berkas tambahan  ',
        ]]]);
        $this->artisan('telegram:poll', ['--once' => true])->assertExitCode(0);
        $this->assertSame('Berkas tambahan', $ticket->messages()->sole()->message);
        $this->assertSame('ID: 123', $ticket->fresh()->citizen_contact);
        Http::assertSentCount(3);
    }

    public function test_photo_without_active_ticket_creates_ticket_even_when_download_fails(): void
    {
        $this->fakeUpdates([['update_id' => 9, 'message' => [
            'message_id' => 2, 'chat' => ['id' => 123], 'from' => ['first_name' => 'Naufal'],
            'photo' => [['file_id' => 'small'], ['file_id' => 'large']],
        ]]]);
        $this->artisan('telegram:poll', ['--once' => true])->assertExitCode(0);
        $ticket = ChatTicket::sole();
        $this->assertSame('telegram-123', $ticket->session_id);
        $this->assertSame('open', $ticket->status);
        $this->assertSame(2, $ticket->messages()->count());
        Http::assertSent(fn ($r) => str_contains($r->url(), 'getFile') && $r['file_id'] === 'large');
        Http::assertSent(fn ($r) => str_contains($r->url(), 'sendMessage') && str_contains($r['text'], $ticket->ticket_number));
    }
}
