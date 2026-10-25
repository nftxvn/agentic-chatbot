<?php

namespace App\Services\Tickets;

use App\Models\ChatTicket;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Database\Eloquent\Collection;

/** Query antrean/detail/percakapan; controller tetap menentukan input dan pembungkus HTTP. */
class TicketQueryService
{
    public function paginate(array $filters, int $perPage): LengthAwarePaginator
    {
        $query = ChatTicket::with(['assignedAdmin:id,name,email'])
            ->orderBy('last_message_at', 'desc')
            ->orderBy('id', 'desc');

        // Filter status
        if (array_key_exists('status', $filters) && $filters['status'] !== 'all') {
            $query->where('status', $filters['status']);
        }

        // Filter priority
        if (array_key_exists('priority', $filters) && $filters['priority'] !== 'all') {
            $query->where('priority', $filters['priority']);
        }

        // Filter channel
        if (array_key_exists('channel', $filters) && $filters['channel'] !== 'all') {
            $query->where('channel', $filters['channel']);
        }

        // Search across ticket number, citizen name/contact/agency, issue summary
        if (array_key_exists('search', $filters)) {
            $search = trim($filters['search']);
            $query->where(function ($q) use ($search) {
                $q->where('ticket_number', 'like', "%{$search}%")
                  ->orWhere('citizen_name', 'like', "%{$search}%")
                  ->orWhere('citizen_contact', 'like', "%{$search}%")
                  ->orWhere('citizen_agency', 'like', "%{$search}%")
                  ->orWhere('issue_summary', 'like', "%{$search}%");
            });
        }

        return $query->paginate($perPage);
    }

    public function stats(): array
    {
        return [
            'total' => ChatTicket::count(),
            'open' => ChatTicket::where('status', 'open')->count(),
            'in_progress' => ChatTicket::where('status', 'in_progress')->count(),
            'resolved' => ChatTicket::where('status', 'resolved')->count(),
            'closed' => ChatTicket::where('status', 'closed')->count(),
        ];
    }

    public function findWithConversation(int $id): ChatTicket
    {
        return ChatTicket::with([
            'assignedAdmin:id,name,email',
            'messages.sender:id,name,email',
        ])->findOrFail($id);
    }

    public function messages(ChatTicket $ticket): Collection
    {
        return $ticket->messages()
            ->with('sender:id,name,email')
            ->orderBy('created_at', 'asc')
            ->get();
    }
}
