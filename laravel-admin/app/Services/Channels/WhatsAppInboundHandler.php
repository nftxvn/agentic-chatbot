<?php

namespace App\Services\Channels;

use App\Models\AppSetting;
use App\Services\Settings\ChatbotSettingsService;
use Illuminate\Support\Facades\Log;

class WhatsAppInboundHandler
{
    public function __construct(private AiChatGateway $ai)
    {
    }

    public function handle(array $payload, string $aiBaseUrl, string $aiToken, callable $sendReply): ChannelResponse
    {
        // 1. Cek apakah layanan WhatsApp aktif
        $isActive = AppSetting::getVal('wa_status', 'false') === 'true';
        if (!$isActive) {
            Log::info('Pesan WhatsApp diabaikan karena status WhatsApp chatbot sedang nonaktif.');
            return new ChannelResponse(['status' => 'ignored', 'reason' => 'whatsapp_disabled']);
        }

        // 2. Ekstraksi nomor pengirim dan isi pesan dari berbagai format gateway
        $from = null;
        $messageText = null;

        // A. Format Meta WhatsApp Cloud API
        $metaMessages = data_get($payload, 'entry.0.changes.0.value.messages');
        if (is_array($metaMessages) && !empty($metaMessages)) {
            $firstMsg = $metaMessages[0];
            $from = $firstMsg['from'] ?? null;
            $messageText = $firstMsg['text']['body'] ?? null;
        }

        // B. Format Generic / Fonnte / Wablas / Custom Gateway
        if (!$messageText) {
            $from = data_get($payload, 'sender') ?? data_get($payload, 'phone') ?? data_get($payload, 'from') ?? $from;
            $messageText = data_get($payload, 'message') ?? data_get($payload, 'text') ?? data_get($payload, 'body');
        }

        if (empty($from) || empty($messageText)) {
            return new ChannelResponse(['status' => 'ignored', 'reason' => 'no_text_or_sender']);
        }

        Log::info('Pesan WhatsApp Masuk', [
            'from' => $from,
            'message' => substr($messageText, 0, 80),
        ]);

        $sessionId = 'wa-' . preg_replace('/[^0-9]/', '', $from);

        // 3. Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = \App\Models\ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        if ($activeTicket) {
            // Auto-enrich ticket metadata (Nama, Instansi, Kendala) from ongoing message
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $messageText);

            if (empty($activeTicket->citizen_contact)) {
                $activeTicket->citizen_contact = $from;
            }

            $senderDisplayName = $activeTicket->citizen_name ?: 'Warga WhatsApp';

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

            Log::info('Pesan WhatsApp diteruskan langsung ke Live Chat (Human Takeover)', [
                'ticket_id' => $activeTicket->id,
                'from' => $from,
                'citizen_name' => $senderDisplayName,
                'message' => substr($messageText, 0, 80),
            ]);

            return new ChannelResponse([
                'status' => 'forwarded_to_live_chat',
                'ticket_id' => $activeTicket->id,
            ]);
        }

        // 4. Panggil RAG Engine di Python AI
        $systemPrompt = AppSetting::getVal('rag_system_prompt', ChatbotSettingsService::getDefaultRagPrompt());
        $temperature = (float) AppSetting::getVal('rag_temperature', '0.2');
        $topK = (int) AppSetting::getVal('rag_top_k', '8');
        $citationEnabled = AppSetting::getVal('rag_citation_enabled', 'true') === 'true';

        try {
            $response = $this->ai->postMessage($aiBaseUrl . '/api/chat/message', $aiToken, [
                'message' => $messageText,
                'phone_number' => $from,
                'session_id' => $sessionId,
                'system_prompt' => $systemPrompt,
                'temperature' => $temperature,
                'top_k' => $topK,
            ]);

            if (!$response->successful()) {
                Log::error('RAG Engine gagal memproses pesan WhatsApp', [
                    'status' => $response->status(),
                    'body' => $response->body(),
                ]);
                return new ChannelResponse(['status' => 'error', 'message' => 'AI processing failed'], 500);
            }

            $aiData = $response->json();
            $replyText = $aiData['reply'] ?? '';
            $sources = $aiData['sources'] ?? [];

            // 4. Format jawaban untuk WhatsApp (teks rapi dengan rujukan)
            $formattedReply = $replyText;

            if ($citationEnabled && !empty($sources) && !str_contains($replyText, 'Rujukan:')) {
                $formattedReply .= "\n\n*Rujukan Dokumen SOP:*";
                foreach ($sources as $source) {
                    $docName = $source['doc_name'] ?? ('Dokumen #' . $source['document_id']);
                    $pageStr = !empty($source['page']) ? " (Hal. {$source['page']})" : '';
                    $formattedReply .= "\n• {$docName}{$pageStr}";
                }
            }

            // 5. Kirim balasan ke WhatsApp Gateway jika API URL & Token terpasang
            $sendReply($from, $formattedReply);

            // 6. Catat telemetri interaksi WhatsApp (Privasi warga terlindungi: tanpa nomor HP dan tanpa isi pesan)
            $isFallback = str_contains($replyText, 'terhubung dengan petugas') || str_contains($replyText, 'menindaklanjuti pesan') || str_contains($replyText, 'menindaklanjuti percakapan');
            \App\Models\ChatLog::create([
                'session_id' => $sessionId,
                'channel' => 'whatsapp',
                'api_key_id' => null,
                'sender_identifier' => 'Pengguna WhatsApp',
                'query' => null,
                'answer' => null,
                'sources_json' => !empty($sources) ? ['count' => count($sources)] : null,
                'is_fallback' => $isFallback,
                'response_time_ms' => null,
            ]);

            return new ChannelResponse([
                'status' => 'success',
                'session_id' => $sessionId,
                'recipient' => $from,
            ]);
        } catch (\Exception $e) {
            Log::error('Exception saat memproses webhook WhatsApp', ['error' => $e->getMessage()]);
            return new ChannelResponse(['status' => 'error', 'message' => $e->getMessage()], 500);
        }
    }
}
