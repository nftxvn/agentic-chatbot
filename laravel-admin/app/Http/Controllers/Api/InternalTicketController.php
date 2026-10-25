<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\Tickets\TicketIngestionService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class InternalTicketController extends Controller
{
    /**
     * Ingestion endpoint for human escalation from Python AI Service.
     * POST /api/v1/internal/chat-tickets
     */
    public function storeOrUpdate(Request $request, TicketIngestionService $tickets): JsonResponse
    {
        $validated = $request->validate([
            'session_id' => 'required|string|max:255',
            'ticket_id' => 'nullable|integer|exists:chat_tickets,id',
            'message' => 'required|string',
            'intent' => 'nullable|string|max:100',
            'citizen_name' => 'nullable|string|max:150',
            'citizen_contact' => 'nullable|string|max:150',
            'citizen_agency' => 'nullable|string|max:150',
            'issue_summary' => 'nullable|string',
            'channel' => 'nullable|string|max:50',
        ]);

        $ticket = $tickets->ingest($validated);
        $created = $ticket->wasRecentlyCreated;

        return response()->json([
            'success' => true,
            'message' => $created ? 'Ticket created successfully' : 'Ticket updated successfully',
            'data' => [
                'ticket_id' => $ticket->id,
                'ticket_number' => $ticket->ticket_number,
                'status' => $ticket->status,
                'session_id' => $ticket->session_id,
                'created_at' => $ticket->created_at->toISOString(),
            ],
        ], $created ? 201 : 200);
    }
}
