<?php

namespace App\Http\Controllers\Api;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Http\Controllers\Controller;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TicketController extends Controller
{
    /**
     * GET /api/tickets
     * List tickets with filters (status, search, priority, channel) and pagination.
     */
    public function index(Request $request): JsonResponse
    {
        $query = ChatTicket::with(['assignedAdmin:id,name,email'])
            ->orderBy('last_message_at', 'desc')
            ->orderBy('id', 'desc');

        // Filter status
        if ($request->filled('status') && $request->status !== 'all') {
            $query->where('status', $request->status);
        }

        // Filter priority
        if ($request->filled('priority') && $request->priority !== 'all') {
            $query->where('priority', $request->priority);
        }

        // Filter channel
        if ($request->filled('channel') && $request->channel !== 'all') {
            $query->where('channel', $request->channel);
        }

        // Search across ticket number, citizen name/contact/agency, issue summary
        if ($request->filled('search')) {
            $search = trim($request->search);
            $query->where(function ($q) use ($search) {
                $q->where('ticket_number', 'like', "%{$search}%")
                  ->orWhere('citizen_name', 'like', "%{$search}%")
                  ->orWhere('citizen_contact', 'like', "%{$search}%")
                  ->orWhere('citizen_agency', 'like', "%{$search}%")
                  ->orWhere('issue_summary', 'like', "%{$search}%");
            });
        }

        $perPage = min(max((int) $request->input('per_page', 15), 5), 100);
        $tickets = $query->paginate($perPage);

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
        $stats = [
            'total' => ChatTicket::count(),
            'open' => ChatTicket::where('status', 'open')->count(),
            'in_progress' => ChatTicket::where('status', 'in_progress')->count(),
            'resolved' => ChatTicket::where('status', 'resolved')->count(),
            'closed' => ChatTicket::where('status', 'closed')->count(),
        ];

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
        $ticket = ChatTicket::with([
            'assignedAdmin:id,name,email',
            'messages.sender:id,name,email',
        ])->findOrFail($id);

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
        $ticket->assigned_admin_id = $adminId;

        // Auto transition open ticket to in_progress upon assignment
        if ($ticket->status === 'open') {
            $ticket->status = 'in_progress';
        }

        $ticket->save();
        $ticket->load('assignedAdmin:id,name,email');

        event(new TicketUpdated($ticket));

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
        $newStatus = $validated['status'];

        $ticket->status = $newStatus;

        if ($newStatus === 'resolved') {
            $ticket->resolved_at = now();
        } elseif ($newStatus === 'closed') {
            $ticket->closed_at = now();
        } elseif ($newStatus === 'open' || $newStatus === 'in_progress') {
            $ticket->resolved_at = null;
            $ticket->closed_at = null;
        }

        $ticket->save();
        $ticket->load('assignedAdmin:id,name,email');

        event(new TicketUpdated($ticket));

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

        $messages = $ticket->messages()
            ->with('sender:id,name,email')
            ->orderBy('created_at', 'asc')
            ->get();

        return response()->json([
            'success' => true,
            'data' => $messages,
        ]);
    }

    /**
     * POST /api/tickets/{id}/messages
     * Send agent response or internal note.
     */
    public function reply(Request $request, int $id): JsonResponse
    {
        $validated = $request->validate([
            'message' => 'required|string',
            'is_internal_note' => 'nullable|boolean',
            'attachments' => 'nullable|array',
        ]);

        $ticket = ChatTicket::findOrFail($id);
        $user = $request->user();
        $isInternal = (bool) ($validated['is_internal_note'] ?? false);

        $message = $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $user?->id,
            'sender_name' => $user?->name ?: 'Petugas Helpdesk',
            'message' => $validated['message'],
            'attachments' => $validated['attachments'] ?? null,
            'is_internal_note' => $isInternal,
        ]);

        // If not internal note:
        if (!$isInternal) {
            if ($ticket->status === 'open') {
                $ticket->status = 'in_progress';
            }
            if (empty($ticket->assigned_admin_id) && $user) {
                $ticket->assigned_admin_id = $user->id;
            }
        }

        $ticket->last_message_at = now();
        $ticket->save();
        $ticket->load('assignedAdmin:id,name,email');

        $message->load('sender:id,name,email');

        // Dispatch real-time events
        event(new TicketMessageSent($message));
        event(new TicketUpdated($ticket));

        return response()->json([
            'success' => true,
            'message' => 'Message sent successfully',
            'data' => $message,
        ], 201);
    }
}
