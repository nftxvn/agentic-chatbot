<?php

namespace App\Services\Tickets;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\ChatTicket;
use Illuminate\Support\Collection;

/**
 * Penugasan, transisi status, dan penghapusan tiket.
 * Callback cleanup mempertahankan hook protected controller beserta urutan efek lama.
 */
class TicketLifecycleService
{
    public function assign(ChatTicket $ticket, mixed $adminId): ChatTicket
    {
        $ticket->assigned_admin_id = $adminId;

        // Auto transition open ticket to in_progress upon assignment
        if ($ticket->status === 'open') {
            $ticket->status = 'in_progress';
        }

        $ticket->save();
        $ticket->load('assignedAdmin:id,name,email');

        event(new TicketUpdated($ticket));

        return $ticket;
    }

    public function transition(ChatTicket $ticket, string $newStatus, mixed $senderId, callable $forgetSession): ChatTicket
    {
        $oldStatus = $ticket->status;

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

        // Record and emit system message flags
        if ($newStatus === 'resolved' || $newStatus === 'closed') {
            // Bersihkan memori sesi AI di Redis agar saat warga chat kembali, sesi AI langsung bersih dari awal
            $forgetSession($ticket->session_id, $ticket->id);

            $systemMsg = $ticket->messages()->create([
                'sender_type' => 'system',
                'sender_id' => $senderId,
                'sender_name' => 'Sistem Helpdesk',
                'message' => "Ticket Closed: {$ticket->ticket_number}",
                'is_internal_note' => false,
            ]);
            event(new TicketMessageSent($systemMsg));
        } elseif (($newStatus === 'in_progress' || $newStatus === 'open') && ($oldStatus === 'resolved' || $oldStatus === 'closed')) {
            $systemMsg = $ticket->messages()->create([
                'sender_type' => 'system',
                'sender_id' => $senderId,
                'sender_name' => 'Sistem Helpdesk',
                'message' => "Ticket Re-opened: {$ticket->ticket_number}",
                'is_internal_note' => false,
            ]);
            event(new TicketMessageSent($systemMsg));
        }

        event(new TicketUpdated($ticket));

        return $ticket;
    }

    public function delete(ChatTicket $ticket, mixed $actorId, callable $forgetSession): void
    {
        $id = $ticket->id;
        $sessionId = $ticket->session_id;
        $ticketNumber = $ticket->ticket_number;

        // 1. Delete attached files from local private storage
        try {
            \Illuminate\Support\Facades\Storage::disk('local')->deleteDirectory("private/tickets/{$ticket->id}");
        } catch (\Exception $e) {
            \Illuminate\Support\Facades\Log::warning("Gagal menghapus folder berkas tiket #{$ticket->id}: " . $e->getMessage());
        }

        // 2. Clean up AI session memory in Redis (best-effort).
        $forgetSession($sessionId, $ticket->id);

        // 3. Delete ticket records (messages cascade delete automatically)
        $ticket->delete();

        \Illuminate\Support\Facades\Log::info("Tiket {$ticketNumber} (#{$id}) berhasil dihapus oleh admin ID: " . ($actorId ?? 'unknown'));
    }

    public function bulkDelete(Collection $tickets, mixed $actorId, callable $forgetSession): int
    {
        $deletedCount = 0;

        foreach ($tickets as $ticket) {
            try {
                \Illuminate\Support\Facades\Storage::disk('local')->deleteDirectory("private/tickets/{$ticket->id}");
            } catch (\Exception $e) {
                // Ignore
            }

            $forgetSession($ticket->session_id, $ticket->id);

            $ticket->delete();
            $deletedCount++;
        }

        \Illuminate\Support\Facades\Log::info("Sebanyak {$deletedCount} tiket berhasil dihapus massal oleh admin ID: " . ($actorId ?? 'unknown'));

        return $deletedCount;
    }
}
