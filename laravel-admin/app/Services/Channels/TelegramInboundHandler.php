<?php

namespace App\Services\Channels;

use App\Models\AppSetting;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Log;

class TelegramInboundHandler
{
    public function handle(array $payload, callable $reply): ChannelResponse
    {
        $isActive = AppSetting::getVal('telegram_status', 'false') === 'true';
        if (!$isActive) {
            Log::info('Pesan Telegram diabaikan karena status Telegram bot sedang nonaktif.');
            return new ChannelResponse(['status' => 'ignored', 'reason' => 'telegram_disabled']);
        }

        // 1. Anti-Looping / Deduplikasi Update Telegram (Mencegah retry otomatis Telegram saat respon AI > 5 detik)
        $updateId = data_get($payload, 'update_id');
        if ($updateId) {
            $lockKey = "telegram:update:{$updateId}";
            if (!Cache::add($lockKey, 1, 180)) {
                Log::info("Pesan Telegram duplikat diabaikan (Update ID #{$updateId} sedang/sudah diproses).");
                return new ChannelResponse(['status' => 'ignored', 'reason' => 'duplicate_update_id']);
            }
        }

        $chatId = data_get($payload, 'message.chat.id') ?? data_get($payload, 'edited_message.chat.id');
        $messageId = data_get($payload, 'message.message_id') ?? data_get($payload, 'edited_message.message_id');
        $messageText = trim(data_get($payload, 'message.text') ?? data_get($payload, 'message.caption') ?? '');
        $fromName = data_get($payload, 'message.from.first_name', 'User');

        if ($chatId && $messageId) {
            $msgLockKey = "telegram:msg:{$chatId}:{$messageId}";
            if (!Cache::add($msgLockKey, 1, 180)) {
                Log::info("Pesan Telegram duplikat diabaikan (Chat #{$chatId}, Msg #{$messageId}).");
                return new ChannelResponse(['status' => 'ignored', 'reason' => 'duplicate_message_id']);
            }
        }

        if (empty($chatId) || empty($messageText)) {
            return new ChannelResponse(['status' => 'ignored', 'reason' => 'no_text_or_chat_id']);
        }

        if ($messageText === '/start' || $messageText === '/reset' || $messageText === '/help') {
            try {
                \Illuminate\Support\Facades\Redis::connection()->select(2);
                \Illuminate\Support\Facades\Redis::del("chatbot:session:telegram-{$chatId}");
            } catch (\Exception $e) {
                // Ignore
            }
            $messageText = 'Halo';
        }

        Log::info('Pesan Telegram Masuk', [
            'chat_id' => $chatId,
            'from' => $fromName,
            'message' => substr($messageText, 0, 80),
        ]);

        $encryptedToken = AppSetting::getVal('telegram_bot_token', '');
        if (empty($encryptedToken)) {
            Log::error('Bot Token Telegram belum dikonfigurasi saat webhook dipanggil.');
            return new ChannelResponse(['status' => 'error', 'reason' => 'missing_bot_token']);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            Log::error('Gagal mendekripsi Bot Token Telegram: ' . $e->getMessage());
            return new ChannelResponse(['status' => 'error', 'reason' => 'decrypt_failed']);
        }

        $fromUsername = data_get($payload, 'message.from.username');
        $sessionId = 'telegram-' . $chatId;

        // 3. Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = \App\Models\ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        if ($activeTicket) {
            // Auto-enrich ticket metadata (Nama, Instansi, Kendala) from ongoing message
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $messageText, $fromName);

            if (empty($activeTicket->citizen_contact)) {
                $activeTicket->citizen_contact = $fromUsername ? "@{$fromUsername} (ID: {$chatId})" : "ID: {$chatId}";
            }

            $senderDisplayName = $activeTicket->citizen_name ?: ($fromName ?: 'Warga Telegram');

            $msg = $activeTicket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $senderDisplayName,
                'message' => $messageText,
                'is_internal_note' => false,
            ]);

            $activeTicket->last_message_at = now();
            $activeTicket->save();

            event(new \App\Events\TicketMessageSent($msg));
            event(new \App\Events\TicketUpdated($activeTicket));

            Log::info('Pesan Telegram diteruskan langsung ke Live Chat (Human Takeover)', [
                'ticket_id' => $activeTicket->id,
                'chat_id' => $chatId,
                'from' => $senderDisplayName,
                'message' => substr($messageText, 0, 80),
            ]);

            return new ChannelResponse([
                'status' => 'forwarded_to_live_chat',
                'ticket_id' => $activeTicket->id,
            ]);
        }

        $reply($token, $chatId, $messageText, $fromName, $fromUsername);

        return new ChannelResponse(['status' => 'success']);
    }
}
