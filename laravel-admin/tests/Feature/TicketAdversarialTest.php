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

class TicketAdversarialTest extends TestCase
{
    use RefreshDatabase;

    protected string $validToken = 'dev-internal-token-secret-1234567890';

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.ai_microservice.token' => $this->validToken]);
    }

    // =========================================================================
    // 1. Internal Endpoint: Token Security & Timing Attack Resilience
    // =========================================================================

    public function test_internal_token_tampered_and_edge_cases(): void
    {
        $payload = ['session_id' => 'sess-test', 'message' => 'Test message'];

        // 1. Missing Authorization header completely
        $this->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401)
            ->assertJson(['success' => false]);

        // 2. Trailing whitespace in token
        $this->withHeader('Authorization', 'Bearer ' . $this->validToken . ' ')
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 3. Uppercase version (tokens are case-sensitive)
        $this->withHeader('Authorization', 'Bearer ' . strtoupper($this->validToken))
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 4. Truncated token (checking timing attack resilience / exact match)
        $this->withHeader('Authorization', 'Bearer ' . substr($this->validToken, 0, -2))
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 5. Malformed prefix (no space after Bearer)
        $this->withHeader('Authorization', 'Bearer' . $this->validToken)
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 6. Empty Bearer token
        $this->withHeader('Authorization', 'Bearer ')
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 7. Invalid custom header token
        $this->withHeader('X-Internal-Token', 'invalid-token-here')
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        $this->withHeader('X-AI-Service-Token', 'invalid-token-here')
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(401);

        // 8. Valid token in X-AI-Service-Token succeeds
        $this->withHeader('X-AI-Service-Token', $this->validToken)
            ->postJson('/api/v1/internal/chat-tickets', $payload)
            ->assertStatus(201);
    }

    // =========================================================================
    // 2. Internal Endpoint: Malformed Payloads & Type Boundary Ingestion
    // =========================================================================

    public function test_internal_validation_malformed_and_boundary_types(): void
    {
        $headers = ['Authorization' => 'Bearer ' . $this->validToken];

        // 1. Missing session_id
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', ['message' => 'hello'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['session_id']);

        // 2. Non-string session_id (array)
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', ['session_id' => ['nested' => 'id'], 'message' => 'hello'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['session_id']);

        // 3. session_id exceeding 255 chars
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', ['session_id' => str_repeat('a', 256), 'message' => 'hello'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['session_id']);

        // 4. Missing message
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', ['session_id' => 'valid-sess'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['message']);

        // 5. Non-string message (array)
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', ['session_id' => 'valid-sess', 'message' => ['text' => 'malformed']])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['message']);

        // 6. Overly long string fields (> 150 chars)
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'valid-sess',
                'message' => 'hello',
                'citizen_name' => str_repeat('b', 151),
                'citizen_contact' => str_repeat('c', 151),
                'citizen_agency' => str_repeat('d', 151),
            ])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['citizen_name', 'citizen_contact', 'citizen_agency']);

        // 7. Non-existent ticket_id (foreign existence check)
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'valid-sess',
                'ticket_id' => 999999,
                'message' => 'Follow up on nonexistent ticket',
            ])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['ticket_id']);

        // 8. Non-integer ticket_id (string)
        $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'valid-sess',
                'ticket_id' => 'non-numeric-id',
                'message' => 'Follow up',
            ])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['ticket_id']);
    }

    // =========================================================================
    // 3. Internal Endpoint: Special Characters, Emojis, XSS & SQLi Resilience
    // =========================================================================

    public function test_internal_special_characters_and_xss_injection(): void
    {
        $headers = ['Authorization' => 'Bearer ' . $this->validToken];

        $xssName = "<script>alert('XSS-NAME')</script>";
        $sqliIssue = "' OR 1=1; DROP TABLE chat_tickets; --";
        $emojiMessage = "Halo Tim Helpdesk Diskominfotik! 👋🇮🇩 Saya mengalami kendala SPBE 🚨🔥 Mohon bantuannya 🙏";

        $response = $this->withHeaders($headers)
            ->postJson('/api/v1/internal/chat-tickets', [
                'session_id' => 'sess-xss-sqli-test',
                'citizen_name' => $xssName,
                'citizen_contact' => '081234567890',
                'citizen_agency' => "Bidang IT & Cyber ' OR '1'='1",
                'issue_summary' => $sqliIssue,
                'message' => $emojiMessage,
            ]);

        $response->assertStatus(201)
            ->assertJson(['success' => true]);

        $ticketId = $response->json('data.ticket_id');

        // Verify stored without corruption
        $ticket = ChatTicket::find($ticketId);
        $this->assertNotNull($ticket);
        $this->assertEquals($xssName, $ticket->citizen_name);
        $this->assertEquals($sqliIssue, $ticket->issue_summary);

        $msg = $ticket->messages()->first();
        $this->assertNotNull($msg);
        $this->assertEquals($emojiMessage, $msg->message);
    }

    // =========================================================================
    // 4. High Volume Ticket Creation & Unique Number Sequence
    // =========================================================================

    public function test_internal_rapid_burst_and_unique_ticket_number_generation(): void
    {
        Event::fake([TicketCreated::class, TicketMessageSent::class]);
        $headers = ['Authorization' => 'Bearer ' . $this->validToken];

        $ticketNumbers = [];
        $burstCount = 30;

        for ($i = 1; $i <= $burstCount; $i++) {
            $response = $this->withHeaders($headers)
                ->postJson('/api/v1/internal/chat-tickets', [
                    'session_id' => 'rapid-session-' . $i,
                    'message' => 'Pesan antrean nomor ' . $i,
                    'citizen_name' => 'Warga ' . $i,
                ]);

            $response->assertStatus(201);
            $number = $response->json('data.ticket_number');
            $this->assertNotNull($number);
            $this->assertStringStartsWith('TICK-', $number);
            $this->assertNotContains($number, $ticketNumbers, "Duplicate ticket number detected: {$number}");
            $ticketNumbers[] = $number;
        }

        $this->assertCount($burstCount, array_unique($ticketNumbers));
        $this->assertEquals($burstCount, ChatTicket::count());
    }

    // =========================================================================
    // 5. Session State Transitions: Reusing vs Creating on Resolved/Closed
    // =========================================================================

    public function test_internal_session_reuse_and_status_isolation(): void
    {
        $headers = ['Authorization' => 'Bearer ' . $this->validToken];
        $sessionId = 'sess-cycle-123';

        // 1. First message creates ticket T1
        $res1 = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Pertanyaan awal',
        ]);
        $res1->assertStatus(201);
        $t1Id = $res1->json('data.ticket_id');

        // 2. Second message while open -> reuses T1
        $res2 = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Follow up 1',
        ]);
        $res2->assertStatus(200);
        $this->assertEquals($t1Id, $res2->json('data.ticket_id'));

        // 3. Mark T1 as 'resolved'
        $t1 = ChatTicket::find($t1Id);
        $t1->status = 'resolved';
        $t1->save();

        // 4. Third message from citizen -> should NOT append to resolved ticket; creates new ticket T2!
        $res3 = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Saya mau buka keluhan baru',
        ]);
        $res3->assertStatus(201);
        $t2Id = $res3->json('data.ticket_id');
        $this->assertNotEquals($t1Id, $t2Id);

        // 5. Mark T2 as 'closed'
        $t2 = ChatTicket::find($t2Id);
        $t2->status = 'closed';
        $t2->save();

        // 6. Fourth message from citizen -> creates new ticket T3!
        $res4 = $this->withHeaders($headers)->postJson('/api/v1/internal/chat-tickets', [
            'session_id' => $sessionId,
            'message' => 'Keluhan ketiga',
        ]);
        $res4->assertStatus(201);
        $t3Id = $res4->json('data.ticket_id');
        $this->assertNotEquals($t2Id, $t3Id);
    }

    // =========================================================================
    // 6. Admin REST API: Invalid Status Transitions & Timestamp State Machine
    // =========================================================================

    public function test_admin_status_transition_adversarial_values(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create([
            'session_id' => 'sess-status-adversarial',
            'status' => 'open',
        ]);

        // 1. Invalid status names
        $invalidStatuses = ['pending', 'deleted', 'OPEN', 'in-progress', 'archived', '1', ''];
        foreach ($invalidStatuses as $badStatus) {
            $response = $this->actingAs($admin)
                ->patchJson("/api/tickets/{$ticket->id}/status", [
                    'status' => $badStatus,
                ]);
            $response->assertStatus(422)
                ->assertJsonValidationErrors(['status']);
        }

        // 2. Non-string status (array)
        $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", ['status' => ['resolved']])
            ->assertStatus(422);

        // 3. Valid status state machine cycle
        // open -> in_progress
        $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", ['status' => 'in_progress'])
            ->assertStatus(200);
        $ticket->refresh();
        $this->assertEquals('in_progress', $ticket->status);
        $this->assertNull($ticket->resolved_at);

        // in_progress -> resolved (sets resolved_at)
        $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", ['status' => 'resolved'])
            ->assertStatus(200);
        $ticket->refresh();
        $this->assertEquals('resolved', $ticket->status);
        $this->assertNotNull($ticket->resolved_at);

        // resolved -> closed (sets closed_at)
        $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", ['status' => 'closed'])
            ->assertStatus(200);
        $ticket->refresh();
        $this->assertEquals('closed', $ticket->status);
        $this->assertNotNull($ticket->closed_at);

        // closed -> open (clears resolved_at and closed_at)
        $this->actingAs($admin)
            ->patchJson("/api/tickets/{$ticket->id}/status", ['status' => 'open'])
            ->assertStatus(200);
        $ticket->refresh();
        $this->assertEquals('open', $ticket->status);
        $this->assertNull($ticket->resolved_at);
        $this->assertNull($ticket->closed_at);
    }

    // =========================================================================
    // 7. Admin REST API: Assignment to Nonexistent / Invalid Admin IDs
    // =========================================================================

    public function test_admin_assign_adversarial_values(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create([
            'session_id' => 'sess-assign-adversarial',
            'status' => 'open',
        ]);

        // 1. Assign to nonexistent admin ID
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", ['admin_id' => 999999])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['admin_id']);

        // 2. Assign to negative admin ID
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", ['admin_id' => -1])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['admin_id']);

        // 3. Assign with string
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", ['admin_id' => 'not-an-id'])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['admin_id']);

        // 4. Valid assignment assigns correctly and transitions status to in_progress
        $targetUser = User::factory()->create();
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/assign", ['admin_id' => $targetUser->id])
            ->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'assigned_admin_id' => $targetUser->id,
                    'status' => 'in_progress',
                ],
            ]);

        $ticket->refresh();
        $this->assertEquals($targetUser->id, $ticket->assigned_admin_id);
        $this->assertEquals('in_progress', $ticket->status);
    }

    // =========================================================================
    // 8. Admin REST API: Reply Edge Cases (Empty, Internal Note, Long Text)
    // =========================================================================

    public function test_admin_reply_adversarial_values(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create([
            'session_id' => 'sess-reply-adversarial',
            'status' => 'open',
        ]);

        // 1. Missing message
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", [])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['message']);

        // 2. Empty string message
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", ['message' => ''])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['message']);

        // 3. Non-boolean is_internal_note (array)
        $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", [
                'message' => 'Valid message',
                'is_internal_note' => ['invalid'],
            ])
            ->assertStatus(422)
            ->assertJsonValidationErrors(['is_internal_note']);

        // 4. Very long response text (10,000 characters)
        $longMessage = str_repeat('Jawaban resmi petugas diskominfotik. ', 300);
        $response = $this->actingAs($admin)
            ->postJson("/api/tickets/{$ticket->id}/messages", [
                'message' => $longMessage,
            ]);
        $response->assertStatus(201);

        $ticket->refresh();
        $this->assertEquals('in_progress', $ticket->status);
        $this->assertEquals($admin->id, $ticket->assigned_admin_id);
    }

    // =========================================================================
    // 9. Admin REST API: Search SQL Injection & Wildcard Resilience
    // =========================================================================

    public function test_admin_search_adversarial_queries(): void
    {
        $admin = User::factory()->create();

        ChatTicket::create([
            'session_id' => 's-safe-1',
            'citizen_name' => 'Aditya Pratama',
            'issue_summary' => 'Masalah antrean puskesmas',
        ]);

        // SQL injection probe
        $sqliResponse = $this->actingAs($admin)
            ->getJson("/api/tickets?search=" . urlencode("' OR '1'='1' --"));
        $sqliResponse->assertStatus(200)
            ->assertJson(['success' => true]);

        // Wildcard character probe
        $wildcardResponse = $this->actingAs($admin)
            ->getJson("/api/tickets?search=" . urlencode("%%%___"));
        $wildcardResponse->assertStatus(200)
            ->assertJson(['success' => true]);

        // Extreme length search query (1000 characters)
        $longSearch = str_repeat('x', 1000);
        $longResponse = $this->actingAs($admin)
            ->getJson("/api/tickets?search=" . urlencode($longSearch));
        $longResponse->assertStatus(200)
            ->assertJson(['pagination' => ['total' => 0]]);
    }

    // =========================================================================
    // 10. Admin REST API: Pagination Boundary Values
    // =========================================================================

    public function test_admin_pagination_boundary_values(): void
    {
        $admin = User::factory()->create();

        for ($i = 0; $i < 10; $i++) {
            ChatTicket::create(['session_id' => 'sess-p-' . $i, 'citizen_name' => 'Warga ' . $i]);
        }

        // per_page = 0 should be clamped to min 5
        $res0 = $this->actingAs($admin)->getJson('/api/tickets?per_page=0');
        $res0->assertStatus(200);
        $this->assertEquals(5, $res0->json('pagination.per_page'));

        // per_page = -10 should be clamped to min 5
        $resNeg = $this->actingAs($admin)->getJson('/api/tickets?per_page=-10');
        $resNeg->assertStatus(200);
        $this->assertEquals(5, $resNeg->json('pagination.per_page'));

        // per_page = 500 should be clamped to max 100
        $resHuge = $this->actingAs($admin)->getJson('/api/tickets?per_page=500');
        $resHuge->assertStatus(200);
        $this->assertEquals(100, $resHuge->json('pagination.per_page'));
    }

    // =========================================================================
    // 11. Admin REST API: 404 on Nonexistent Ticket ID
    // =========================================================================

    public function test_admin_nonexistent_ticket_endpoints(): void
    {
        $admin = User::factory()->create();

        $this->actingAs($admin)->getJson('/api/tickets/9999999')->assertStatus(404);
        $this->actingAs($admin)->postJson('/api/tickets/9999999/assign', [])->assertStatus(404);
        $this->actingAs($admin)->patchJson('/api/tickets/9999999/status', ['status' => 'resolved'])->assertStatus(404);
        $this->actingAs($admin)->getJson('/api/tickets/9999999/messages')->assertStatus(404);
        $this->actingAs($admin)->postJson('/api/tickets/9999999/messages', ['message' => 'test'])->assertStatus(404);
    }

    // =========================================================================
    // 12. Dynamic Unread Message Count Calculation
    // =========================================================================

    public function test_unread_messages_count_dynamic_calculation(): void
    {
        $admin = User::factory()->create();
        $ticket = ChatTicket::create(['session_id' => 'sess-unread-calc', 'status' => 'open']);

        // 3 citizen messages
        $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'm1']);
        $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'm2']);
        $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'm3']);

        $ticket->refresh();
        $this->assertEquals(3, $ticket->unread_messages_count);

        // Admin replies
        $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'sender_name' => $admin->name,
            'message' => 'Admin reply',
        ]);

        $ticket->refresh();
        $this->assertEquals(0, $ticket->unread_messages_count);

        // Citizen sends 2 more messages
        $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'm4']);
        $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'm5']);

        $ticket->refresh();
        $this->assertEquals(2, $ticket->unread_messages_count);

        // Admin sends internal note (is_internal_note = true, sender_type = agent)
        // Note: internal notes are agent sender type, but should not disrupt unread count if we test it:
        $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $admin->id,
            'sender_name' => $admin->name,
            'message' => 'Internal note',
            'is_internal_note' => true,
        ]);
        // After an agent message, unread count is 0
        $ticket->refresh();
        $this->assertEquals(0, $ticket->unread_messages_count);
    }
}
