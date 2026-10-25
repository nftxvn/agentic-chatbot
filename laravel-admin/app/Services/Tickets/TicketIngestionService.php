<?php

namespace App\Services\Tickets;

use App\Events\TicketCreated;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use App\Services\EntityExtractorService;
use Illuminate\Support\Str;

class TicketIngestionService
{
    /**
     * Persist a validated escalation while preserving the existing reuse policy.
     * The returned model's wasRecentlyCreated flag distinguishes creation from reuse.
     */
    public function ingest(array $input): ChatTicket
    {
        $details = $this->citizenDetails($input);
        $ticket = $this->findTicket($input, $details['citizen_contact']);

        if ($this->canReuse($ticket)) {
            return $this->appendToTicket($ticket, $input['message'], $details);
        }

        return $this->openTicket($input, $details);
    }

    private function citizenDetails(array $input): array
    {
        $name = $input['citizen_name'] ?? null;
        $contact = $input['citizen_contact'] ?? null;
        $agency = $input['citizen_agency'] ?? null;
        $summary = $input['issue_summary'] ?? null;

        $history = EntityExtractorService::extractFromSessionHistory($input['session_id'], $name);
        $message = EntityExtractorService::extractFromText($input['message'], $name);

        if (empty($name)) {
            $name = $message['name'] ?: ($history['name'] ?? null);
        }
        if (empty($agency)) {
            $agency = $message['agency'] ?: ($history['agency'] ?? null);
        }
        if (empty($summary) || strtolower(trim($summary)) === strtolower(trim($input['message']))) {
            $summary = $message['issue_summary'] ?: ($history['issue_summary'] ?: Str::limit($input['message'], 150));
        }
        if (empty($contact)) {
            $contact = $message['contact'] ?: ($history['contact'] ?? null);
        }

        return [
            'citizen_name' => $name,
            'citizen_contact' => $contact,
            'citizen_agency' => $agency,
            'issue_summary' => $summary,
        ];
    }

    private function findTicket(array $input, ?string $contact): ?ChatTicket
    {
        if (!empty($input['ticket_id'])) {
            $ticket = ChatTicket::find($input['ticket_id']);
            if ($ticket) {
                return $ticket;
            }
        }

        return ChatTicket::where(function ($query) use ($input, $contact) {
            $query->where('session_id', $input['session_id']);
            if (!empty($contact)) {
                $query->orWhere('citizen_contact', $contact);
            }
        })->latest('id')->first();
    }

    private function canReuse(?ChatTicket $ticket): bool
    {
        if (!$ticket) {
            return false;
        }

        return in_array($ticket->status, ['open', 'in_progress'])
            || $ticket->created_at?->isToday()
            || $ticket->resolved_at?->isToday();
    }

    private function appendToTicket(ChatTicket $ticket, string $text, array $details): ChatTicket
    {
        $wasResolved = in_array($ticket->status, ['resolved', 'closed']);
        if ($wasResolved) {
            $ticket->status = 'in_progress';
            $ticket->resolved_at = null;
            $ticket->closed_at = null;
        }

        foreach ($details as $field => $value) {
            if (!empty($value)) {
                $ticket->{$field} = $value;
            }
        }

        $ticket->last_message_at = now();
        $ticket->save();

        if ($wasResolved) {
            event(new TicketMessageSent($this->createMessage(
                $ticket, 'system', 'Sistem Helpdesk', "Ticket Re-opened: {$ticket->ticket_number}",
            )));
        }

        $message = $this->createMessage(
            $ticket, 'citizen', $details['citizen_name'] ?: ($ticket->citizen_name ?: 'Warga'), $text,
        );
        event(new TicketMessageSent($message));
        event(new TicketUpdated($ticket));

        return $ticket;
    }

    private function openTicket(array $input, array $details): ChatTicket
    {
        $ticket = ChatTicket::create([
            'session_id' => $input['session_id'],
            'citizen_name' => $details['citizen_name'],
            'citizen_contact' => $details['citizen_contact'],
            'citizen_agency' => $details['citizen_agency'],
            'channel' => $input['channel'] ?? 'widget',
            'status' => 'open',
            'priority' => 'medium',
            'issue_summary' => $details['issue_summary'] ?? Str::limit($input['message'], 150),
            'last_message_at' => now(),
        ]);

        event(new TicketMessageSent($this->createMessage(
            $ticket, 'system', 'Sistem Helpdesk', "Ticket Opened: {$ticket->ticket_number}",
        )));

        $message = $this->createMessage(
            $ticket, 'citizen', $details['citizen_name'] ?: 'Warga', $input['message'],
        );
        event(new TicketCreated($ticket));
        event(new TicketMessageSent($message));

        return $ticket;
    }

    private function createMessage(ChatTicket $ticket, string $type, string $sender, string $text): ChatTicketMessage
    {
        return $ticket->messages()->create([
            'sender_type' => $type,
            'sender_id' => null,
            'sender_name' => $sender,
            'message' => $text,
            'is_internal_note' => false,
        ]);
    }
}
