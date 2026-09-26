<?php

namespace App\Http\Controllers\Api;

use App\Events\TicketCreated;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Http\Controllers\Controller;
use App\Models\ChatTicket;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class InternalTicketController extends Controller
{
    /**
     * Ingestion endpoint for human escalation from Python AI Service.
     * POST /api/v1/internal/chat-tickets
     */
    public function storeOrUpdate(Request $request): JsonResponse
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

        $ticket = null;

        // 1. If explicit ticket_id supplied, locate that ticket
        if (!empty($validated['ticket_id'])) {
            $ticket = ChatTicket::find($validated['ticket_id']);
        }

        // 2. Otherwise, check if active ticket exists for this session
        if (!$ticket) {
            $ticket = ChatTicket::where('session_id', $validated['session_id'])
                ->whereIn('status', ['open', 'in_progress'])
                ->latest('id')
                ->first();
        }

        $citizenName = $validated['citizen_name'] ?? null;
        $citizenContact = $validated['citizen_contact'] ?? null;
        $citizenAgency = $validated['citizen_agency'] ?? null;
        $issueSummary = $validated['issue_summary'] ?? null;
        $channel = $validated['channel'] ?? 'widget';

        if ($ticket) {
            // Update metadata if new contact details arrived
            $updated = false;
            if (!empty($citizenName) && empty($ticket->citizen_name)) {
                $ticket->citizen_name = $citizenName;
                $updated = true;
            }
            if (!empty($citizenContact) && empty($ticket->citizen_contact)) {
                $ticket->citizen_contact = $citizenContact;
                $updated = true;
            }
            if (!empty($citizenAgency) && empty($ticket->citizen_agency)) {
                $ticket->citizen_agency = $citizenAgency;
                $updated = true;
            }
            if (!empty($issueSummary) && empty($ticket->issue_summary)) {
                $ticket->issue_summary = $issueSummary;
                $updated = true;
            }

            $ticket->last_message_at = now();
            $ticket->save();

            // Append citizen followup message
            $message = $ticket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $citizenName ?: ($ticket->citizen_name ?: 'Warga'),
                'message' => $validated['message'],
                'is_internal_note' => false,
            ]);

            // Dispatch real-time events
            event(new TicketMessageSent($message));
            event(new TicketUpdated($ticket));

            return response()->json([
                'success' => true,
                'message' => 'Ticket updated successfully',
                'data' => [
                    'ticket_id' => $ticket->id,
                    'ticket_number' => $ticket->ticket_number,
                    'status' => $ticket->status,
                    'session_id' => $ticket->session_id,
                    'created_at' => $ticket->created_at->toISOString(),
                ],
            ], 200);
        }

        // 3. Create fresh ticket
        $ticket = ChatTicket::create([
            'session_id' => $validated['session_id'],
            'citizen_name' => $citizenName,
            'citizen_contact' => $citizenContact,
            'citizen_agency' => $citizenAgency,
            'channel' => $channel,
            'status' => 'open',
            'priority' => 'medium',
            'issue_summary' => $issueSummary ?? Str::limit($validated['message'], 150),
            'last_message_at' => now(),
        ]);

        $message = $ticket->messages()->create([
            'sender_type' => 'citizen',
            'sender_id' => null,
            'sender_name' => $citizenName ?: 'Warga',
            'message' => $validated['message'],
            'is_internal_note' => false,
        ]);

        // Dispatch real-time events
        event(new TicketCreated($ticket));
        event(new TicketMessageSent($message));

        return response()->json([
            'success' => true,
            'message' => 'Ticket created successfully',
            'data' => [
                'ticket_id' => $ticket->id,
                'ticket_number' => $ticket->ticket_number,
                'status' => $ticket->status,
                'session_id' => $ticket->session_id,
                'created_at' => $ticket->created_at->toISOString(),
            ],
        ], 201);
    }
}
