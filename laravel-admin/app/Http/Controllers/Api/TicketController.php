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
        $oldStatus = $ticket->status;
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

        // Record and emit system message flags
        if ($newStatus === 'resolved' || $newStatus === 'closed') {
            // Bersihkan memori sesi AI di Redis agar saat warga chat kembali, sesi AI langsung bersih dari awal
            try {
                \Illuminate\Support\Facades\Redis::connection()->select(2);
                \Illuminate\Support\Facades\Redis::del("chatbot:session:{$ticket->session_id}");
            } catch (\Exception $e) {
                // Ignore Redis cleanup errors
            }

            $systemMsg = $ticket->messages()->create([
                'sender_type' => 'system',
                'sender_id' => $request->user()?->id,
                'sender_name' => 'Sistem Helpdesk',
                'message' => "Ticket Closed: {$ticket->ticket_number}",
                'is_internal_note' => false,
            ]);
            event(new TicketMessageSent($systemMsg));
        } elseif (($newStatus === 'in_progress' || $newStatus === 'open') && ($oldStatus === 'resolved' || $oldStatus === 'closed')) {
            $systemMsg = $ticket->messages()->create([
                'sender_type' => 'system',
                'sender_id' => $request->user()?->id,
                'sender_name' => 'Sistem Helpdesk',
                'message' => "Ticket Re-opened: {$ticket->ticket_number}",
                'is_internal_note' => false,
            ]);
            event(new TicketMessageSent($systemMsg));
        }

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
     * Send agent response or internal note with optional file attachment.
     */
    public function reply(Request $request, int $id): JsonResponse
    {
        $validated = $request->validate([
            'message' => 'nullable|string',
            'is_internal_note' => 'nullable|boolean',
            'attachments' => 'nullable|array',
            'file' => 'nullable|file|max:10240', // Max 10MB
        ]);

        $ticket = ChatTicket::findOrFail($id);
        $user = $request->user();
        $isInternal = (bool) ($validated['is_internal_note'] ?? false);

        $attachments = $validated['attachments'] ?? [];

        // Handle uploaded file if present
        if ($request->hasFile('file')) {
            $fileAttachment = \App\Services\AttachmentService::optimizeAndSave(
                $request->file('file'),
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
            return response()->json([
                'success' => false,
                'message' => 'Pesan atau lampiran tidak boleh kosong.',
            ], 422);
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

        // Dispatch outbound message to external channels (Telegram / WhatsApp)
        if (!$isInternal) {
            $this->dispatchOutboundMessage($ticket, $messageText, $attachments);
        }

        // Dispatch real-time events
        event(new TicketMessageSent($message));
        event(new TicketUpdated($ticket));

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
     * Dispatch agent reply to external channels (Telegram, WhatsApp).
     */
    protected function dispatchOutboundMessage(ChatTicket $ticket, string $replyText, array $attachments = []): void
    {
        $channel = strtolower($ticket->channel ?? 'web');
        $contact = $ticket->citizen_contact;
        $sessionId = $ticket->session_id;

        // 1. Channel: Telegram
        if ($channel === 'telegram' || str_starts_with($sessionId, 'telegram-')) {
            $chatId = $contact ?: str_replace('telegram-', '', $sessionId);
            if (!empty($chatId)) {
                $encryptedToken = \App\Models\AppSetting::getVal('telegram_bot_token', '');
                if (!empty($encryptedToken)) {
                    try {
                        $token = \Illuminate\Support\Facades\Crypt::decryptString($encryptedToken);

                        // If has image attachment, send photo natively
                        $hasPhoto = false;
                        foreach ($attachments as $att) {
                            if (!empty($att['file_path']) && str_starts_with($att['mime_type'] ?? '', 'image/')) {
                                $caption = ($replyText !== '[Lampiran Berkas]' && $replyText !== '[Lampiran Foto]') ? $replyText : null;
                                \App\Services\AttachmentService::sendPhotoToTelegram($token, $chatId, $att['file_path'], $caption);
                                $hasPhoto = true;
                                break;
                            }
                        }

                        // Send text message if no photo sent with caption
                        if (!$hasPhoto) {
                            \Illuminate\Support\Facades\Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                                'chat_id' => $chatId,
                                'text' => $replyText,
                            ]);
                        }
                        \Illuminate\Support\Facades\Log::info("Balasan admin berhasil dikirim ke Telegram ({$chatId}).");
                    } catch (\Exception $e) {
                        \Illuminate\Support\Facades\Log::error("Gagal mengirim balasan admin ke Telegram: " . $e->getMessage());
                    }
                }
            }
        }

        // 2. Channel: WhatsApp
        if ($channel === 'whatsapp' || str_starts_with($sessionId, 'wa-') || str_starts_with($sessionId, 'whatsapp-')) {
            $phone = $contact ?: preg_replace('/[^0-9]/', '', $sessionId);
            if (!empty($phone)) {
                try {
                    $waController = new \App\Http\Controllers\Api\V1\WhatsAppWebhookController();
                    $waController->sendWhatsAppMessage($phone, $replyText);
                    \Illuminate\Support\Facades\Log::info("Balasan admin berhasil dikirim ke WhatsApp ({$phone}).");
                } catch (\Exception $e) {
                    \Illuminate\Support\Facades\Log::error("Gagal mengirim balasan admin ke WhatsApp: " . $e->getMessage());
                }
            }
        }
    }
}
