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

        $citizenName = $validated['citizen_name'] ?? null;
        $citizenContact = $validated['citizen_contact'] ?? null;
        $citizenAgency = $validated['citizen_agency'] ?? null;
        $issueSummary = $validated['issue_summary'] ?? null;
        $channel = $validated['channel'] ?? 'widget';

        $ticket = null;

        // 1. If explicit ticket_id supplied, locate that ticket
        if (!empty($validated['ticket_id'])) {
            $ticket = ChatTicket::find($validated['ticket_id']);
        }

        // 2. Otherwise, check latest ticket for this session or contact
        if (!$ticket) {
            $ticket = ChatTicket::where(function ($query) use ($validated, $citizenContact) {
                $query->where('session_id', $validated['session_id']);
                if (!empty($citizenContact)) {
                    $query->orWhere('citizen_contact', $citizenContact);
                }
            })
            ->latest('id')
            ->first();
        }

        // Option B: Reuse ticket if Active (open/in_progress) OR if Resolved/Closed TODAY (same day)
        $isSameDay = $ticket && ($ticket->created_at?->isToday() || $ticket->resolved_at?->isToday());
        $canReuseTicket = $ticket && (in_array($ticket->status, ['open', 'in_progress']) || $isSameDay);

        if ($canReuseTicket) {
            $wasResolved = in_array($ticket->status, ['resolved', 'closed']);

            if ($wasResolved) {
                $ticket->status = 'in_progress';
                $ticket->resolved_at = null;
                $ticket->closed_at = null;
            }

            // Update metadata if new contact details arrived
            if (!empty($citizenName)) $ticket->citizen_name = $citizenName;
            if (!empty($citizenContact)) $ticket->citizen_contact = $citizenContact;
            if (!empty($citizenAgency)) $ticket->citizen_agency = $citizenAgency;
            if (!empty($issueSummary)) $ticket->issue_summary = $issueSummary;

            $ticket->last_message_at = now();
            $ticket->save();

            // System Separator Flag: Ticket Re-opened
            if ($wasResolved) {
                $reopenMsg = $ticket->messages()->create([
                    'sender_type' => 'system',
                    'sender_id' => null,
                    'sender_name' => 'Sistem Helpdesk',
                    'message' => "Ticket Re-opened: {$ticket->ticket_number}",
                    'is_internal_note' => false,
                ]);
                event(new TicketMessageSent($reopenMsg));
            }

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

        // 3. Create fresh ticket (new citizen or new day case)
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

        // System Separator Flag: Ticket Opened
        $openedMsg = $ticket->messages()->create([
            'sender_type' => 'system',
            'sender_id' => null,
            'sender_name' => 'Sistem Helpdesk',
            'message' => "Ticket Opened: {$ticket->ticket_number}",
            'is_internal_note' => false,
        ]);
        event(new TicketMessageSent($openedMsg));

        // Citizen First Message
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
