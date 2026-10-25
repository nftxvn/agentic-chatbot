<?php

namespace App\Services\Channels;

use App\Models\ChatTicket;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use Illuminate\Support\Facades\Http;

class TelegramPollingMessageHandler
{
    public function handle(array $update, string $token, bool $isActive, string $aiBaseUrl, string $aiToken, callable $write, callable $reply): void
    {
        $message = $update['message'] ?? $update['edited_message'] ?? null;
        if (!$message) {
            return;
        }

        $chatId = $message['chat']['id'] ?? null;
        $text = trim($message['text'] ?? $message['caption'] ?? '');
        $fromName = $message['from']['first_name'] ?? 'Pengguna';
        $username = $message['from']['username'] ?? null;

        $rawName = trim(preg_replace('/[.\s]+/', ' ', $fromName ?? ''));
        $displayName = !empty($rawName) ? $rawName : 'Warga';

        if (!$chatId) {
            return;
        }

        // Deteksi Lampiran Foto atau Dokumen Gambar
        $photoArray = $message['photo'] ?? null;
        $docObj = $message['document'] ?? null;
        $photoFileId = null;

        if (!empty($photoArray) && is_array($photoArray)) {
            $bestPhoto = end($photoArray);
            $photoFileId = $bestPhoto['file_id'] ?? null;
        } elseif (!empty($docObj) && str_starts_with($docObj['mime_type'] ?? '', 'image/')) {
            $photoFileId = $docObj['file_id'] ?? null;
        }

        // Tangani pesan non-teks tanpa gambar (stiker, audio, voice, kontak)
        if (empty($text) && empty($photoFileId)) {
            $write('line', "[Telegram] Pesan non-teks dari {$displayName} (Chat ID: {$chatId}). Mengirim petunjuk format...");
            try {
                Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                    'chat_id' => $chatId,
                    'text' => "Halo {$displayName}! Saat ini Asisten Virtual Diskominfotik baru dapat melayani pertanyaan dalam bentuk pesan teks dan foto/tangkapan layar.\n\nSilakan ketik pertanyaan Anda atau kirimkan screenshot kendala.",
                ]);
            } catch (\Exception $e) {
                // Ignore
            }
            return;
        }

        // Normalisasi command /start, /reset, atau /help
        if ($text === '/start' || $text === '/reset' || $text === '/help') {
            // Bersihkan sesi memori AI di Redis agar dimulai dari lembaran baru
            try {
                \Illuminate\Support\Facades\Redis::connection()->select(2);
                \Illuminate\Support\Facades\Redis::del("chatbot:session:telegram-{$chatId}");
            } catch (\Exception $e) {
                // Ignore
            }
            $text = 'Halo';
        }

        $write('line', "[Telegram] Pesan dari {$fromName} (Chat ID: {$chatId})" . (!empty($photoFileId) ? ' [Lampiran Foto]' : '') . ": {$text}");

        if (!$isActive) {
            $write('warn', '  -> Status Telegram sedang Nonaktif di Web Admin. Pesan diabaikan.');
            return;
        }

        $sessionId = 'telegram-' . $chatId;

        // Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        // 1. KONDISI: Ada Tiket Aktif (Pesan Teks / Foto langsung diteruskan ke Petugas)
        if ($activeTicket) {
            // Auto-enrich ticket metadata (Nama, Instansi, Kendala) from ongoing message
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $text, $fromName);

            if (empty($activeTicket->citizen_contact)) {
                $activeTicket->citizen_contact = $username ? "@{$username} (ID: {$chatId})" : "ID: {$chatId}";
            }

            $senderDisplayName = $activeTicket->citizen_name ?: ($fromName ?: 'Warga Telegram');

            $attachments = [];
            if (!empty($photoFileId)) {
                $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $activeTicket->id, $text);
                if ($att) {
                    $attachments[] = $att;
                }
            }

            $msgText = !empty($text) ? $text : (!empty($attachments) ? '[Lampiran Foto]' : '-');

            $msg = $activeTicket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $senderDisplayName,
                'message' => $msgText,
                'attachments' => !empty($attachments) ? $attachments : null,
                'is_internal_note' => false,
            ]);

            $activeTicket->last_message_at = now();
            $activeTicket->save();

            event(new TicketMessageSent($msg));
            event(new TicketUpdated($activeTicket));

            $write('info', "  -> [Human Takeover] Tiket aktif #{$activeTicket->ticket_number} terdeteksi. Pesan " . (!empty($attachments) ? '& Foto ' : '') . "diteruskan ke Live Chat Petugas.");
            return;
        }

        // 2. KONDISI: User Mengirim FOTO saat belum ada tiket aktif
        // -> Foto HANYA diproses oleh Petugas (Bypass AI 100%, Otomatis Buat / Buka Tiket)
        if (!empty($photoFileId)) {
            $write('info', "  -> [Foto Masuk] Foto hanya diproses oleh Petugas. Membuka tiket Live Chat baru/re-open...");

            // Cek apakah ada tiket sesi ini hari ini untuk di-reopen
            $existingToday = ChatTicket::where('session_id', $sessionId)
                ->whereDate('created_at', today())
                ->latest('id')
                ->first();

            $targetTicket = null;

            if ($existingToday) {
                $existingToday->status = 'in_progress';
                $existingToday->resolved_at = null;
                $existingToday->closed_at = null;
                $existingToday->last_message_at = now();
                $existingToday->save();

                $reopenMsg = $existingToday->messages()->create([
                    'sender_type' => 'system',
                    'sender_id' => null,
                    'sender_name' => 'Sistem Helpdesk',
                    'message' => "Ticket Re-opened: {$existingToday->ticket_number}",
                    'is_internal_note' => false,
                ]);
                event(new TicketMessageSent($reopenMsg));

                $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $existingToday->id, $text);
                $msg = $existingToday->messages()->create([
                    'sender_type' => 'citizen',
                    'sender_id' => null,
                    'sender_name' => $displayName,
                    'message' => !empty($text) ? $text : '[Lampiran Foto]',
                    'attachments' => $att ? [$att] : null,
                    'is_internal_note' => false,
                ]);

                event(new TicketMessageSent($msg));
                event(new TicketUpdated($existingToday));
                $targetTicket = $existingToday;
            } else {
                $newTicket = ChatTicket::create([
                    'session_id' => $sessionId,
                    'citizen_name' => $displayName,
                    'citizen_contact' => (string) $chatId,
                    'citizen_agency' => $username ? "@{$username}" : null,
                    'channel' => 'telegram',
                    'status' => 'open',
                    'priority' => 'medium',
                    'issue_summary' => !empty($text) ? $text : 'Lampiran foto kendala warga via Telegram',
                    'last_message_at' => now(),
                ]);

                $openMsg = $newTicket->messages()->create([
                    'sender_type' => 'system',
                    'sender_id' => null,
                    'sender_name' => 'Sistem Helpdesk',
                    'message' => "Ticket Opened: {$newTicket->ticket_number}",
                    'is_internal_note' => false,
                ]);

                event(new \App\Events\TicketCreated($newTicket));
                event(new TicketMessageSent($openMsg));

                $att = \App\Services\AttachmentService::downloadTelegramPhoto($token, $photoFileId, $newTicket->id, $text);
                $msg = $newTicket->messages()->create([
                    'sender_type' => 'citizen',
                    'sender_id' => null,
                    'sender_name' => $displayName,
                    'message' => !empty($text) ? $text : '[Lampiran Foto]',
                    'attachments' => $att ? [$att] : null,
                    'is_internal_note' => false,
                ]);

                event(new TicketMessageSent($msg));
                event(new TicketUpdated($newTicket));
                $targetTicket = $newTicket;
            }

            // Kirim konfirmasi tiket ke Telegram warga
            try {
                Http::timeout(10)->post("https://api.telegram.org/bot{$token}/sendMessage", [
                    'chat_id' => $chatId,
                    'text' => "Halo {$displayName}! Foto tangkapan layar kendala Anda telah kami teruskan ke Petugas Live Chat Helpdesk (Tiket #{$targetTicket->ticket_number}).\n\nPetugas kami akan segera meninjau dan merespons Anda di sini.",
                ]);
            } catch (\Exception $e) {
                // Ignore
            }

            $write('info', "  -> Tiket #{$targetTicket->ticket_number} berhasil diterbitkan & foto dikirim ke dashboard Petugas.");
            return;
        }

        // 3. KONDISI: Pesan TEKS biasa saat belum ada tiket -> Masuk ke Asisten AI (RAG)
        $write('line', '  -> Menghubungkan ke Python AI Engine (Mode Streaming)...');

        $reply(
            $token,
            $chatId,
            $text,
            $fromName,
            $username,
            $aiBaseUrl,
            $aiToken,
            function ($level, $msg) use ($write) {
                if ($level === 'error') $write('error', "  -> {$msg}");
                elseif ($level === 'warn') $write('warn', "  -> {$msg}");
                else $write('line', "  -> {$msg}");
            }
        );

        $write('info', "  -> Balasan selesai distreaming ke {$fromName}!");
    }
}
