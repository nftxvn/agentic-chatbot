<?php

namespace Tests\Feature;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Http\Controllers\Api\TicketController;
use App\Models\ChatTicket;
use App\Models\User;
use App\Services\Tickets\TicketReplyDeliveryService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Redis;
use Illuminate\Support\Facades\Storage;
use Mockery;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class TicketWorkflowContractTest extends TestCase
{
    use RefreshDatabase;

    private User $admin;

    protected function setUp(): void
    {
        parent::setUp();
        $this->admin = User::factory()->create();
        $this->actingAs($this->admin);
        Event::fake([TicketMessageSent::class, TicketUpdated::class]);
        Storage::fake('local');
        RecordingTicketController::$cleanupCalls = [];
    }

    public static function transitions(): array
    {
        return [
            'resolve' => ['open', 'resolved', 'Ticket Closed:', true, false, true],
            'close after resolve' => ['resolved', 'closed', 'Ticket Closed:', true, true, true],
            'reopen' => ['closed', 'open', 'Ticket Re-opened:', false, false, false],
            'assign status' => ['open', 'in_progress', null, false, false, false],
            'repeat close' => ['closed', 'closed', 'Ticket Closed:', false, true, true],
        ];
    }

    #[DataProvider('transitions')]
    public function test_status_transition_preserves_timestamps_system_message_and_cleanup(
        string $old, string $new, ?string $messagePrefix, bool $resolved, bool $closed, bool $cleanup,
    ): void {
        $ticket = ChatTicket::create(['session_id' => 'transition-session', 'status' => $old,
            'resolved_at' => $old === 'resolved' ? now()->subDay() : null,
            'closed_at' => $old === 'closed' ? now()->subDay() : null]);
        if ($cleanup) {
            $connection = Mockery::mock();
            Redis::shouldReceive('connection')->once()->andReturn($connection);
            $connection->shouldReceive('select')->once()->with(2)->ordered();
            $connection->shouldReceive('del')->once()->with('chatbot:session:transition-session')->ordered();
        } else {
            Redis::shouldReceive('connection')->never();
        }

        $this->patchJson("/api/tickets/{$ticket->id}/status", ['status' => $new])
            ->assertOk()->assertJsonPath('data.status', $new);

        $ticket->refresh();
        $this->assertSame($resolved, $ticket->resolved_at !== null);
        $this->assertSame($closed, $ticket->closed_at !== null);
        if ($messagePrefix) {
            $message = $ticket->messages()->sole();
            $this->assertSame($messagePrefix.' '.$ticket->ticket_number, $message->message);
            $this->assertSame('system', $message->sender_type);
            $this->assertSame($this->admin->id, $message->sender_id);
            $this->assertFalse($message->is_internal_note);
            Event::assertDispatched(TicketMessageSent::class, 1);
        } else {
            $this->assertSame(0, $ticket->messages()->count());
            Event::assertNotDispatched(TicketMessageSent::class);
        }
        Event::assertDispatched(TicketUpdated::class, 1);
    }

    public function test_assignment_to_closed_ticket_keeps_status_and_null_admin_uses_authenticated_user(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'assignment-session', 'status' => 'closed', 'closed_at' => now()->subDay()]);
        $closedAt = $ticket->closed_at->toISOString();

        $this->postJson("/api/tickets/{$ticket->id}/assign", ['admin_id' => null])->assertOk()
            ->assertJsonPath('data.assigned_admin_id', $this->admin->id)->assertJsonPath('data.status', 'closed');

        $this->assertSame($closedAt, $ticket->fresh()->closed_at->toISOString());
        Event::assertDispatched(TicketUpdated::class, 1);
    }

    public function test_search_or_conditions_remain_grouped_with_status_filter_and_id_tiebreak_order(): void
    {
        $first = ChatTicket::create(['session_id' => 'query-first', 'citizen_name' => 'Budi', 'status' => 'open', 'last_message_at' => '2026-01-01 01:00:00']);
        $second = ChatTicket::create(['session_id' => 'query-second', 'citizen_agency' => 'Budi Agency', 'status' => 'open', 'last_message_at' => '2026-01-01 01:00:00']);
        ChatTicket::create(['session_id' => 'query-closed', 'citizen_name' => 'Budi', 'status' => 'closed']);

        $this->getJson('/api/tickets?status=open&search=Budi&per_page=1')->assertOk()
            ->assertJsonPath('pagination.total', 2)->assertJsonPath('pagination.per_page', 5)
            ->assertJsonPath('data.0.id', $second->id)->assertJsonPath('data.1.id', $first->id);
    }

    public function test_public_reply_to_closed_ticket_is_saved_and_delivered_before_events_without_reopening(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'closed-reply', 'status' => 'closed', 'closed_at' => now()->subDay()]);
        $closedAt = $ticket->closed_at->toISOString();
        $delivery = Mockery::mock(TicketReplyDeliveryService::class);
        $delivery->shouldReceive('deliver')->once()->withArgs(function ($savedTicket, $message) use ($ticket) {
            $this->assertSame($ticket->id, $savedTicket->id);
            $this->assertSame('closed', $savedTicket->fresh()->status);
            $this->assertSame($this->admin->id, $savedTicket->assigned_admin_id);
            $this->assertSame('Balasan admin', $message->fresh()->message);
            Event::assertNotDispatched(TicketMessageSent::class);
            Event::assertNotDispatched(TicketUpdated::class);
            return true;
        });
        $this->app->instance(TicketReplyDeliveryService::class, $delivery);

        $this->postJson("/api/tickets/{$ticket->id}/messages", ['message' => '  Balasan admin  '])
            ->assertCreated()->assertJsonPath('data.message', 'Balasan admin');

        $this->assertSame($closedAt, $ticket->fresh()->closed_at->toISOString());
        Event::assertDispatched(TicketMessageSent::class, 1);
        Event::assertDispatched(TicketUpdated::class, 1);
    }

    public function test_protected_cleanup_override_remains_used_for_status_and_deletion_before_record_is_deleted(): void
    {
        $this->app->bind(TicketController::class, RecordingTicketController::class);
        Redis::shouldReceive('connection')->never();
        $ticket = ChatTicket::create(['session_id' => 'overridden-session']);

        $this->patchJson("/api/tickets/{$ticket->id}/status", ['status' => 'resolved'])->assertOk();
        $this->deleteJson("/api/tickets/{$ticket->id}")->assertOk();

        $this->assertSame([
            ['overridden-session', $ticket->id, 'resolved'],
            ['overridden-session', $ticket->id, 'resolved'],
        ], RecordingTicketController::$cleanupCalls);
        $this->assertNull($ticket->fresh());
    }

    public function test_bulk_delete_continues_after_redis_extension_errors_and_cleans_files_and_messages(): void
    {
        Redis::shouldReceive('connection')->twice()->andThrow(new \Error('synthetic unavailable extension'));
        $tickets = [];
        foreach (['delete-one', 'delete-two'] as $sessionId) {
            $ticket = ChatTicket::create(['session_id' => $sessionId]);
            $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'halo']);
            Storage::disk('local')->put("private/tickets/{$ticket->id}/file.txt", 'synthetic attachment');
            $tickets[] = $ticket;
        }

        $this->postJson('/api/tickets/bulk-delete', ['ids' => array_map(fn ($ticket) => $ticket->id, $tickets)])
            ->assertOk()->assertJsonPath('data.deleted_count', 2);

        foreach ($tickets as $ticket) {
            $this->assertNull($ticket->fresh());
            Storage::disk('local')->assertMissing("private/tickets/{$ticket->id}/file.txt");
            $this->assertSame(0, $ticket->messages()->count());
        }
    }
}

class RecordingTicketController extends TicketController
{
    public static array $cleanupCalls = [];

    protected function forgetAiSessionMemory(?string $sessionId, int $ticketId): void
    {
        self::$cleanupCalls[] = [$sessionId, $ticketId, ChatTicket::findOrFail($ticketId)->status];
    }
}
