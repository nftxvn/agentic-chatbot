<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatTicket;
use App\Services\Tickets\TicketLifecycleService;
use App\Services\Tickets\TicketQueryService;
use App\Services\Tickets\TicketReplyDeliveryService;
use App\Services\Tickets\TicketReplyService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TicketController extends Controller
{
    public function __construct(
        private TicketQueryService $queries,
        private TicketLifecycleService $lifecycle,
        private TicketReplyService $replies,
    ) {
    }

    /**
     * GET /api/tickets
     * List tickets with filters (status, search, priority, channel) and pagination.
     */
    public function index(Request $request): JsonResponse
    {
        $filters = [];
        foreach (['status', 'priority', 'channel', 'search'] as $field) {
            if ($request->filled($field)) {
                $filters[$field] = $request->{$field};
            }
        }

        $perPage = min(max((int) $request->input('per_page', 15), 5), 100);
        $tickets = $this->queries->paginate($filters, $perPage);

        return response()->json([
            'success' => true,
            'data' => $tickets->items(),
            'pagination' => [
                'current_page' => $tickets->currentPage(),
                'last_page' => $tickets->lastPage(),
                'per_page' => $tickets->perPage(),
                'total' => $tickets->total(),
            ],
        ]);
    }

    /**
     * GET /api/tickets/stats
     * Total, open, in_progress, resolved, closed counts.
     */
    public function stats(): JsonResponse
    {
        $stats = $this->queries->stats();

        return response()->json([
            'success' => true,
            'data' => $stats,
        ]);
    }

    /**
     * GET /api/tickets/{id}
     * Single ticket details with conversation messages.
     */
    public function show(int $id): JsonResponse
    {
        $ticket = $this->queries->findWithConversation($id);

        return response()->json([
            'success' => true,
            'data' => $ticket,
        ]);
    }

    /**
     * POST /api/tickets/{id}/assign
     * Assign ticket to staff user.
     */
    public function assign(Request $request, int $id): JsonResponse
    {
        $validated = $request->validate([
            'admin_id' => 'nullable|integer|exists:users,id',
        ]);

        $ticket = ChatTicket::findOrFail($id);

        // Assign to specified admin or the authenticated user
        $adminId = $validated['admin_id'] ?? $request->user()?->id;
        $this->lifecycle->assign($ticket, $adminId);

        return response()->json([
            'success' => true,
            'message' => 'Ticket assigned successfully',
            'data' => [
                'id' => $ticket->id,
                'assigned_admin_id' => $ticket->assigned_admin_id,
                'assigned_admin' => $ticket->assignedAdmin,
                'status' => $ticket->status,
            ],
        ]);
    }

    /**
     * PATCH /api/tickets/{id}/status
     * Transition ticket status.
     */
    public function updateStatus(Request $request, int $id): JsonResponse
    {
        $validated = $request->validate([
            'status' => 'required|string|in:open,in_progress,resolved,closed',
        ]);

        $ticket = ChatTicket::findOrFail($id);
        $this->lifecycle->transition($ticket, $validated['status'], $request->user()?->id, $this->forgetAiSessionMemory(...));

        return response()->json([
            'success' => true,
            'message' => 'Status updated successfully',
            'data' => [
                'id' => $ticket->id,
                'status' => $ticket->status,
                'resolved_at' => $ticket->resolved_at?->toISOString(),
                'closed_at' => $ticket->closed_at?->toISOString(),
            ],
        ]);
    }

    /**
     * GET /api/tickets/{id}/messages
     * Retrieve conversation message thread for a ticket.
     */
    public function messages(int $id): JsonResponse
    {
        $ticket = ChatTicket::findOrFail($id);

        $messages = $this->queries->messages($ticket);

        return response()->json([
            'success' => true,
            'data' => $messages,
        ]);
    }

    /**
     * POST /api/tickets/{id}/messages
     * Send agent response or internal note with optional file attachment.
     */
    public function reply(Request $request, int $id, TicketReplyDeliveryService $delivery): JsonResponse
    {
        $validated = $request->validate([
            'message' => 'nullable|string',
            'is_internal_note' => 'nullable|boolean',
            'attachments' => 'nullable|array',
            'file' => 'nullable|file|max:10240', // Max 10MB
        ]);

        $ticket = ChatTicket::findOrFail($id);
        $user = $request->user();
        $message = $this->replies->storeAndDeliver(
            $ticket, $user, $validated,
            $request->hasFile('file') ? $request->file('file') : null,
            $delivery,
        );

        if ($message === null) {
            return response()->json([
                'success' => false,
                'message' => 'Pesan atau lampiran tidak boleh kosong.',
            ], 422);
        }

        return response()->json([
            'success' => true,
            'message' => 'Message sent successfully',
            'data' => $message,
        ], 201);
    }

    /**
     * GET /api/tickets/{id}/attachments/{filename}
     * Authenticated download and preview of ticket attachments.
     */
    public function downloadAttachment(Request $request, int $id, string $filename)
    {
        $ticket = ChatTicket::findOrFail($id);
        $safeFilename = basename($filename);
        $path = "private/tickets/{$ticket->id}/{$safeFilename}";

        if (!\Illuminate\Support\Facades\Storage::disk('local')->exists($path)) {
            abort(404, 'Lampiran tidak ditemukan.');
        }

        return \Illuminate\Support\Facades\Storage::disk('local')->response($path);
    }

    /**
     * Redis session cleanup is best-effort: a missing PHP Redis extension or
     * an unavailable Redis server must not prevent the MySQL ticket deletion.
     */
    protected function forgetAiSessionMemory(?string $sessionId, int $ticketId): void
    {
        if (empty($sessionId)) {
            return;
        }

        try {
            $connection = \Illuminate\Support\Facades\Redis::connection();
            $connection->select(2);
            $connection->del("chatbot:session:{$sessionId}");
        } catch (\Throwable $exception) {
            \Illuminate\Support\Facades\Log::warning('Gagal membersihkan memori sesi Redis saat menghapus tiket.', [
                'ticket_id' => $ticketId,
                'error' => $exception->getMessage(),
            ]);
        }
    }

    /**
     * DELETE /api/tickets/{id}
     * Delete a single ticket and its associated data/attachments.
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $ticket = ChatTicket::findOrFail($id);
        $ticketNumber = $ticket->ticket_number;
        $this->lifecycle->delete($ticket, $request->user()?->id, $this->forgetAiSessionMemory(...));

        return response()->json([
            'success' => true,
            'message' => "Tiket {$ticketNumber} berhasil dihapus.",
        ]);
    }

    /**
     * POST /api/tickets/bulk-delete
     * Delete multiple tickets by IDs.
     */
    public function bulkDestroy(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'ids' => 'required|array|min:1',
            'ids.*' => 'integer|exists:chat_tickets,id',
        ]);

        $tickets = ChatTicket::whereIn('id', $validated['ids'])->get();
        $deletedCount = $this->lifecycle->bulkDelete($tickets, $request->user()?->id, $this->forgetAiSessionMemory(...));

        return response()->json([
            'success' => true,
            'message' => "{$deletedCount} tiket berhasil dihapus.",
            'data' => [
                'deleted_count' => $deletedCount,
            ],
        ]);
    }
}
