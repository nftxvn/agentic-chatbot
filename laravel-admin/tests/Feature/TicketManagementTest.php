<?php

namespace Tests\Feature;

use App\Events\TicketCreated;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class TicketManagementTest extends TestCase
{
    use RefreshDatabase;

    protected string $internalToken = 'dev-internal-token-secret-1234567890';

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.ai_microservice.token' => $this->internalToken]);
    }

    // =========================================================================
    // 1. Internal Handoff Endpoint Tests (Python AI -> Laravel)
    // =========================================================================

    public function test_internal_endpoint_rejects_unauthorized_requests(): void
    {
        // No token
        $response = $this->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => 'sess-123',
            'message' => 'Halo butuh bantuan manusia',
        ]);
        $response->assertStatus(401)
                 ->assertJson(['success' => false]);

        // Wrong token
        $response = $this->withHeader('Authorization', 'Bearer wrong-token')
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'sess-123',
                'message' => 'Halo butuh bantuan manusia',
            ]);
        $response->assertStatus(401)
                 ->assertJson(['success' => false]);
    }

    public function test_internal_endpoint_creates_ticket_and_dispatches_events(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);

        $payload = [
            'session_id' => 'session-alpha-123',
            'intent' => 'human_escalation',
            'message' => 'Saya ingin bicara dengan petugas terkait kendala SPBE',
            'citizen_name' => 'Budi Santoso',
            'citizen_contact' => '081234567890',
            'citizen_agency' => 'Dinas Pendidikan',
            'issue_summary' => 'Kendala login portal SPBE',
            'channel' => 'widget',
        ];

        $response = $this->withHeader('Authorization', 'Bearer ' . $this->internalToken)
            ->postJson('/api/v1/internal/chat-tickets', $payload);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'message' => 'Ticket created successfully',
            ])
            ->assertJsonStructure([
                'success',
                'message',
                'data' => [
                    'ticket_id',
                    'ticket_number',
                    'status',
                    'session_id',
                    'created_at',
                ],
            ]);

        $ticketId = $response->json('data.ticket_id');

        $this->assertDatabaseHas('chat_tickets', [
            'id' => $ticketId,
            'session_id' => 'session-alpha-123',
            'citizen_name' => 'Budi Santoso',
            'citizen_contact' => '081234567890',
            'citizen_agency' => 'Dinas Pendidikan',
            'status' => 'open',
            'priority' => 'medium',
            'channel' => 'widget',
        ]);

        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticketId,
            'sender_type' => 'citizen',
            'sender_name' => 'Budi Santoso',
            'message' => 'Saya ingin bicara dengan petugas terkait kendala SPBE',
            'is_internal_note' => false,
        ]);

        Event::assertDispatched(TicketCreated::class, function ($event) use ($ticketId) {
            return $event->ticket->id === $ticketId;
        });

        Event::assertDispatched(TicketMessageSent::class, function ($event) use ($ticketId) {
            return $event->message->ticket_id === $ticketId;
        });
    }

    public function test_internal_endpoint_accepts_custom_header_token(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class]);

        $response = $this->withHeader('X-Internal-Token', $this->internalToken)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'sess-custom-hdr',
                'message' => 'Pesan pengujian header internal',
            ]);

        $response->assertStatus(201)
            ->assertJson(['success' => true]);

        $this->assertDatabaseHas('chat_tickets', [
            'session_id' => 'sess-custom-hdr',
            'status' => 'open',
        ]);
    }

    public function test_internal_endpoint_validation_errors(): void
    {
        $response = $this->withHeader('Authorization', 'Bearer ' . $this->internalToken)
            ->postJson('/api/v1/internal/chat-tickets', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['session_id', 'message']);
    }

    public function test_internal_endpoint_appends_message_to_existing_ticket_id(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);

        $ticket = ChatTicket::create([
            'session_id' => 'sess-followup-1',
            'citizen_name' => 'Ahmad',
            'citizen_contact' => '0811223344',
            'status' => 'open',
            'issue_summary' => 'Masalah surat',
        ]);

        $response = $this->withHeader('Authorization', 'Bearer ' . $this->internalToken)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'sess-followup-1',
                'ticket_id' => $ticket->id,
                'intent' => 'human_escalation_followup',
                'message' => 'Lampiran sudah saya kirimkan ke email',
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Ticket updated successfully',
                'data' => [
                    'ticket_id' => $ticket->id,
                ],
            ]);

        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticket->id,
            'sender_type' => 'citizen',
            'message' => 'Lampiran sudah saya kirimkan ke email',
        ]);

        Event::assertNotDispatched(TicketCreated::class);
        Event::assertDispatched(TicketMessageSent::class);
        Event::assertDispatched(TicketUpdated::class);
    }

    public function test_internal_endpoint_reuses_active_session_ticket(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class, TicketUpdated::class]);

        $ticket = ChatTicket::create([
            'session_id' => 'sess-active-reuse',
            'citizen_name' => 'Rina',
            'status' => 'in_progress',
            'issue_summary' => 'Pertanyaan jadwal pertemuan',
        ]);

        // Post without specifying ticket_id, but with same session_id
        $response = $this->withHeader('Authorization', 'Bearer ' . $this->internalToken)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'sess-active-reuse',
                'message' => 'Bisa tolong dicek kembali?',
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'ticket_id' => $ticket->id,
                ],
            ]);

        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticket->id,
            'message' => 'Bisa tolong dicek kembali?',
        ]);
    }

    // =========================================================================
    // 2. Admin REST API Tests (React Frontend -> Laravel)
    // =========================================================================

    public function test_admin_endpoint_requires_authentication(): void
    {
        $response = $this->getJson('/api/tickets');
        $response->assertStatus(401);
    }

    public function test_admin_can_list_tickets_with_pagination(): void
    {
        $admin = User::factory()->create();

        ChatTicket::create([
            'session_id' => 's1',
            'citizen_name' => 'User One',
            'status' => 'open',
            'issue_summary' => 'Issue 1',
        ]);
        ChatTicket::create([
            'session_id' => 's2',
            'citizen_name' => 'User Two',
            'status' => 'in_progress',
            'issue_summary' => 'Issue 2',
        ]);

        $response = $this->actingAs($admin)
            ->getJson('/api/tickets?per_page=10');

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'pagination' => [
                    'total' => 2,
                    'per_page' => 10,
                ],
            ])
            ->assertJsonStructure([
                'success',
                'data' => [
                    '*' => [
                        'id',
                        'ticket_number',
                        'session_id',
                        'citizen_name',
                        'status',
                        'priority',
                        'unread_messages_count',
                        'created_at',
                    ],
                ],
                'pagination',
            ]);
    }

    public function test_admin_can_filter_tickets_by_status(): void
    {
        $admin = User::factory()->create();

        ChatTicket::create(['session_id' => 's1', 'status' => 'open']);
        ChatTicket::create(['session_id' => 's2', 'status' => 'in_progress']);
        ChatTicket::create(['session_id' => 's3', 'status' => 'resolved']);

        $response = $this->actingAs($admin)
            ->getJson('/api/tickets?status=open');

        $response->assertStatus(200)
            ->assertJson(['pagination' => ['total' => 1]]);

        $this->assertEquals('open', $response->json('data.0.status'));
    }

    public function test_admin_can_search_tickets(): void
    {
        $admin = User::factory()->create();

        ChatTicket::create([
            'session_id' => 's1',
            'citizen_name' => 'Siti Nurhaliza',
            'issue_summary' => 'Pertanyaan seputar NIK',
        ]);
        ChatTicket::create([
            'session_id' => 's2',
            'citizen_name' => 'Doni Salman',
            'issue_summary' => 'Pendaftaran izin usaha',
        ]);

        $response = $this->actingAs($admin)
            ->getJson('/api/tickets?search=Nurhaliza');

        $response->assertStatus(200)
            ->assertJson(['pagination' => ['total' => 1]]);
        $this->assertEquals('Siti Nurhaliza', $response->json('data.0.citizen_name'));
    }

    public function test_admin_can_get_ticket_stats(): void
    {
        $admin = User::factory()->create();

        ChatTicket::create(['session_id' => 's1', 'status' => 'open']);
        ChatTicket::create(['session_id' => 's2', 'status' => 'open']);
        ChatTicket::create(['session_id' => 's3', 'status' => 'in_progress']);
        ChatTicket::create(['session_id' => 's4', 'status' => 'resolved']);
        ChatTicket::create(['session_id' => 's5', 'status' => 'closed']);

        $response = $this->actingAs($admin)
            ->getJson('/api/tickets/stats');

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'total' => 5,
                    'open' => 2,
                    'in_progress' => 1,
                    'resolved' => 1,
                    'closed' => 1,
                ],
            ]);
    }

    public function test_admin_can_view_ticket_detail_with_messages(): void
    {
        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-detail',
            'citizen_name' => 'Joko Widodo',
            'status' => 'open',
            'issue_summary' => 'Bantuan teknis portal',
        ]);

        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Joko Widodo',
            'message' => 'Tolong dibantu aktivasi akun',
        ]);

        $response = $this->actingAs($admin)
            ->getJson("/api/tickets/{$ticket->id}");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'id' => $ticket->id,
                    'citizen_name' => 'Joko Widodo',
                    'messages' => [
                        [
                            'message' => 'Tolong dibantu aktivasi akun',
                            'sender_name' => 'Joko Widodo',
                        ],
                    ],
                ],
            ]);
    }

    public function test_admin_can_assign_ticket(): void
    {
        Event::fake([TicketUpdated::class]);

        $admin = User::factory()->create();
        $targetStaff = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-assign',
            'status' => 'open',
        ]);

        $response = $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", [
                'admin_id' => $targetStaff->id,
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'id' => $ticket->id,
                    'assigned_admin_id' => $targetStaff->id,
                    'status' => 'in_progress',
                ],
            ]);

        $this->assertDatabaseHas('chat_tickets', [
            'id' => $ticket->id,
            'assigned_admin_id' => $targetStaff->id,
            'status' => 'in_progress',
        ]);

        Event::assertDispatched(TicketUpdated::class);
    }

    public function test_admin_can_self_assign_ticket(): void
    {
        Event::fake([TicketUpdated::class]);

        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-self-assign',
            'status' => 'open',
        ]);

        $response = $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", []);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'id' => $ticket->id,
                    'assigned_admin_id' => $admin->id,
                    'status' => 'in_progress',
                ],
            ]);

        $this->assertDatabaseHas('chat_tickets', [
            'id' => $ticket->id,
            'assigned_admin_id' => $admin->id,
            'status' => 'in_progress',
        ]);
    }

    public function test_admin_can_update_ticket_status_with_timestamps(): void
    {
        Event::fake([TicketUpdated::class]);

        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-status',
            'status' => 'in_progress',
        ]);

        // Resolve ticket
        $response = $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", [
                'status' => 'resolved',
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'id' => $ticket->id,
                    'status' => 'resolved',
                ],
            ]);

        $ticket->refresh();
        $this->assertEquals('resolved', $ticket->status);
        $this->assertNotNull($ticket->resolved_at);

        Event::assertDispatched(TicketUpdated::class);
    }

    public function test_admin_can_fetch_messages_thread(): void
    {
        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-msg-thread',
            'status' => 'open',
        ]);

        $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Warga',
            'message' => 'Pertanyaan 1',
        ]);
        $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'sender_name' => $admin->name,
            'message' => 'Jawaban 1',
        ]);

        $response = $this->actingAs($admin)
            ->getJson("/api/tickets/{$ticket->id}/messages");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
            ]);

        $this->assertCount(2, $response->json('data'));
    }

    public function test_admin_can_reply_to_ticket_and_dispatches_events(): void
    {
        Event::fake([TicketMessageSent::class, TicketUpdated::class]);

        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-reply',
            'status' => 'open',
        ]);

        $response = $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", [
                'message' => 'Halo Bapak, laporan Anda sudah kami tindak lanjuti.',
                'is_internal_note' => false,
            ]);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'message' => 'Message sent successfully',
                'data' => [
                    'ticket_id' => $ticket->id,
                    'sender_type' => 'agent',
                    'message' => 'Halo Bapak, laporan Anda sudah kami tindak lanjuti.',
                ],
            ]);

        $ticket->refresh();
        $this->assertEquals('in_progress', $ticket->status);
        $this->assertEquals($admin->id, $ticket->assigned_admin_id);

        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticket->id,
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'is_internal_note' => false,
        ]);

        Event::assertDispatched(TicketMessageSent::class, function ($event) use ($ticket) {
            return $event->message->ticket_id === $ticket->id;
        });

        Event::assertDispatched(TicketUpdated::class, function ($event) use ($ticket) {
            return $event->ticket->id === $ticket->id;
        });
    }

    public function test_admin_can_add_internal_note_without_changing_ticket_status(): void
    {
        Event::fake([TicketMessageSent::class, TicketUpdated::class]);

        $admin = User::factory()->create();

        $ticket = ChatTicket::create([
            'session_id' => 's-internal-note',
            'status' => 'open',
        ]);

        $response = $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", [
                'message' => 'Catatan internal: koordinasi ke bidang SPBE sebelum merespons',
                'is_internal_note' => true,
            ]);

        $response->assertStatus(201);

        $ticket->refresh();
        // Internal note must not alter status from open to in_progress
        $this->assertEquals('open', $ticket->status);

        $this->assertDatabaseHas('chat_ticket_messages', [
            'ticket_id' => $ticket->id,
            'is_internal_note' => true,
        ]);
    }

    // =========================================================================
    // 3. Broadcasting Channels & Payload Structure Tests
    // =========================================================================

    public function test_broadcasting_events_payload_and_channels(): void
    {
        $ticket = ChatTicket::create([
            'session_id' => 's-broadcast-check',
            'citizen_name' => 'Dewi',
            'status' => 'open',
        ]);

        $message = $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_name' => 'Dewi',
            'message' => 'Cek broadcast event',
        ]);

        // 1. TicketCreated
        $ticketCreated = new TicketCreated($ticket);
        $this->assertEquals('ticket.created', $ticketCreated->broadcastAs());
        $this->assertContains('tickets', array_map(fn ($c) => $c->name, $ticketCreated->broadcastOn()));
        $createdPayload = $ticketCreated->broadcastWith();
        $this->assertArrayHasKey('ticket', $createdPayload);
        $this->assertEquals($ticket->id, $createdPayload['ticket']->id);

        // 2. TicketMessageSent
        $messageSent = new TicketMessageSent($message);
        $this->assertEquals('message.sent', $messageSent->broadcastAs());
        $this->assertContains("ticket.{$ticket->id}", array_map(fn ($c) => $c->name, $messageSent->broadcastOn()));
        $messagePayload = $messageSent->broadcastWith();
        $this->assertArrayHasKey('message', $messagePayload);
        $this->assertEquals($ticket->id, $messagePayload['ticket_id']);

        // 3. TicketUpdated
        $ticketUpdated = new TicketUpdated($ticket);
        $this->assertEquals('ticket.updated', $ticketUpdated->broadcastAs());
        $this->assertContains('tickets', array_map(fn ($c) => $c->name, $ticketUpdated->broadcastOn()));
        $this->assertContains("ticket.{$ticket->id}", array_map(fn ($c) => $c->name, $ticketUpdated->broadcastOn()));
        $updatedPayload = $ticketUpdated->broadcastWith();
        $this->assertArrayHasKey('ticket', $updatedPayload);
    }
}
