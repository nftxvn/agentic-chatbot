<?php

namespace App\Services\Tickets;

use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use App\Models\ChatTicket;
use App\Models\ChatTicketMessage;
use App\Models\User;
use Illuminate\Http\UploadedFile;

/** Penyimpanan balasan/lampiran, pembaruan tiket, delivery, lalu event sesuai urutan lama. */
class TicketReplyService
{
    public function storeAndDeliver(
        ChatTicket $ticket,
        ?User $user,
        array $validated,
        ?UploadedFile $file,
        TicketReplyDeliveryService $delivery,
    ): ?ChatTicketMessage {
        $isInternal = (bool) ($validated['is_internal_note'] ?? false);

        $attachments = $validated['attachments'] ?? [];

        // Handle uploaded file if present
        if ($file !== null) {
            $fileAttachment = \App\Services\AttachmentService::optimizeAndSave(
                $file,
                $ticket->id
            );
            if ($fileAttachment) {
                $attachments[] = $fileAttachment;
            }
        }

        $messageText = trim($validated['message'] ?? '');
        if (empty($messageText) && !empty($attachments)) {
            $messageText = '[Lampiran Berkas]';
        } elseif (empty($messageText)) {
            return null;
        }

        $message = $ticket->messages()->create([
            'sender_type' => 'agent',
            'sender_id' => $user?->id,
            'sender_name' => $user?->name ?: 'Petugas Helpdesk',
            'message' => $messageText,
            'attachments' => !empty($attachments) ? $attachments : null,
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

        $delivery->deliver($ticket, $message);

        // Dispatch real-time events
        event(new TicketMessageSent($message));
        event(new TicketUpdated($ticket));

        return $message;
    }
}
