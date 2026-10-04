<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Api\SettingController;
use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use App\Models\ChatTicket;
use App\Events\TicketMessageSent;
use App\Events\TicketUpdated;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\StreamedResponse;

class ChatController extends Controller
{
    /**
     * Get Python AI backend base URL
     */
    protected function getAiBaseUrl(): string
    {
        return config('services.ai.url', 'http://localhost:8080');
    }

    /**
     * Token untuk memanggil layanan Python AI.
     *
     * Kuncinya `services.ai_microservice.token` (dari AI_SERVICE_TOKEN di .env) —
     * sesuai config/services.php. Sebelumnya baris ini membaca
     * `services.ai.internal_token`, kunci yang tidak pernah didefinisikan, lalu
     * jatuh ke string default sehingga setiap panggilan ke Python dijawab 401.
     * Kegagalannya senyap karena admin UI lewat proxy Vite yang membawa token
     * sendiri, dan widget memakai endpoint yang autentikasinya dimatikan.
     *
     * Sengaja TIDAK memakai nilai cadangan: token kosong harus terlihat sebagai
     * 401 yang jelas, bukan tersamar sebagai token palsu yang seolah sah.
     */
    protected function getInternalToken(): string
    {
        return (string) config('services.ai_microservice.token');
    }

    /**
     * Build system prompt with active chatbot identity and persona
     */
    protected function buildFullSystemPrompt(): string
    {
        $chatbotName = AppSetting::getVal('chatbot_name', 'Asisten Virtual Diskominfotik');
        $chatbotPersona = AppSetting::getVal('chatbot_persona', 'Asisten AI Resmi Layanan Informasi Diskominfotik');
        $rawPrompt = AppSetting::getVal('rag_system_prompt', SettingController::getDefaultRagPrompt());

        $systemPrompt = str_replace(
            ['{chatbot_name}', '{chatbot_persona}'],
            [$chatbotName, $chatbotPersona],
            $rawPrompt
        );

        if (!str_contains($systemPrompt, $chatbotName)) {
            $systemPrompt = "Identitas: {$chatbotName}\nPersona: {$chatbotPersona}\n\n" . $systemPrompt;
        }

        return $systemPrompt;
    }

    /**
     * POST /api/v1/chat — Non-Streaming Standard JSON Response
     * Cocok untuk WhatsApp bot, CRM, backend integrasi, dan mobile apps.
     */
    public function message(Request $request)
    {
        $validated = $request->validate([
            'query' => 'required|string|min:1|max:2000',
            'session_id' => 'nullable|string|max:100',
            'document_ids' => 'nullable|array',
            'document_ids.*' => 'integer',
        ]);

        $startTime = microtime(true);
        $sessionId = $validated['session_id'] ?? ('session-' . Str::random(16));
        $apiKey = $request->attributes->get('authenticated_api_key');

        // Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        if ($activeTicket) {
            if ($apiKey && !$activeTicket->api_key_id) {
                $activeTicket->api_key_id = $apiKey->id;
            }
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $validated['query']);

            $senderDisplayName = $activeTicket->citizen_name ?: 'Warga';

            $msg = $activeTicket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $senderDisplayName,
                'message' => $validated['query'],
                'is_internal_note' => false,
            ]);

            $activeTicket->last_message_at = now();
            $activeTicket->save();

            event(new TicketMessageSent($msg));
            event(new TicketUpdated($activeTicket));

            return response()->json([
                'success' => true,
                'session_id' => $sessionId,
                'query' => $validated['query'],
                'answer' => 'Pesan Anda telah diteruskan langsung ke Petugas Helpdesk kami. Mohon ditunggu balasan langsung dari petugas.',
                'sources' => [],
                'is_fallback' => false,
                'is_human_takeover' => true,
                'ticket_id' => $activeTicket->id,
                'response_time_ms' => round((microtime(true) - $startTime) * 1000),
            ]);
        }

        // Load active production prompt & parameters configured in dashboard
        $systemPrompt = $this->buildFullSystemPrompt();
        $temperature = (float) AppSetting::getVal('rag_temperature', '0.2');
        $topK = (int) AppSetting::getVal('rag_top_k', '8');

        $payload = [
            'message' => $validated['query'],
            'session_id' => $sessionId,
            'phone_number' => $sessionId,
            'system_prompt' => $systemPrompt,
            'temperature' => $temperature,
            'top_k' => $topK,
            'document_ids' => $validated['document_ids'] ?? null,
        ];

        try {
            $response = Http::withHeaders([
                'Authorization' => 'Bearer ' . $this->getInternalToken(),
                'Content-Type' => 'application/json',
            ])->timeout(60)->post($this->getAiBaseUrl() . '/api/chat/message', $payload);

            if (!$response->successful()) {
                Log::warning('AI Service offline/error on message endpoint, applying graceful degradation', [
                    'status' => $response->status(),
                ]);
                $fallback = \App\Services\GracefulDegradationService::resolveFallback($validated['query']);
                $elapsedMs = round((microtime(true) - $startTime) * 1000);
                return response()->json([
                    'success' => true,
                    'session_id' => $sessionId,
                    'query' => $validated['query'],
                    'answer' => $fallback['answer'],
                    'sources' => $fallback['sources'],
                    'is_fallback' => true,
                    'response_time_ms' => $elapsedMs,
                    'degraded_mode' => true,
                ]);
            }

            $aiData = $response->json();
            $elapsedMs = round((microtime(true) - $startTime) * 1000);
            $answer = $aiData['reply'] ?? '';
            $sources = $aiData['sources'] ?? [];

            // Python dispatches human handoffs back to Laravel before returning its reply.
            // Associate that ticket with the public API key so agent replies can use its webhook.
            $handoffTicket = ChatTicket::where('session_id', $sessionId)
                ->whereIn('status', ['open', 'in_progress'])
                ->latest('id')
                ->first();
            if ($handoffTicket && $apiKey && !$handoffTicket->api_key_id) {
                $handoffTicket->api_key_id = $apiKey->id;
                $handoffTicket->save();
            }
            $isHumanTakeover = (bool) $handoffTicket;

            // Detect fallback if no sources or fallback phrasing
            $isFallback = !$isHumanTakeover && (empty($sources) || str_contains($answer, 'tidak ditemukan'));

            // Record telemetry log (Privacy compliant: no raw query/answer text stored)
            \App\Models\ChatLog::create([
                'session_id' => $sessionId,
                'channel' => 'api_v1',
                'api_key_id' => $apiKey?->id,
                'sender_identifier' => $apiKey?->name ?? 'API Client',
                'query' => null,
                'answer' => null,
                'sources_json' => !empty($sources) ? ['count' => count($sources)] : null,
                'is_fallback' => $isFallback,
                'response_time_ms' => $elapsedMs,
            ]);

            return response()->json([
                'success' => true,
                'session_id' => $sessionId,
                'query' => $validated['query'],
                'answer' => $answer,
                'sources' => $sources,
                'is_fallback' => $isFallback,
                'is_human_takeover' => $isHumanTakeover,
                'ticket_id' => $handoffTicket?->id,
                'ticket_number' => $handoffTicket?->ticket_number,
                'response_time_ms' => $elapsedMs,
            ]);
        } catch (\Exception $e) {
            Log::warning('AI Service unreachable on message endpoint, applying graceful degradation: ' . $e->getMessage());
            $fallback = \App\Services\GracefulDegradationService::resolveFallback($validated['query']);
            $elapsedMs = round((microtime(true) - $startTime) * 1000);
            return response()->json([
                'success' => true,
                'session_id' => $sessionId,
                'query' => $validated['query'],
                'answer' => $fallback['answer'],
                'sources' => $fallback['sources'],
                'is_fallback' => true,
                'response_time_ms' => $elapsedMs,
                'degraded_mode' => true,
            ]);
        }
    }

    /**
     * POST /api/v1/chat/stream — Streaming SSE Response
     * Cocok untuk web widget, chatbot frontend, dan interaksi realtime.
     */
    public function stream(Request $request)
    {
        $validated = $request->validate([
            'query' => 'required|string|min:1|max:2000',
            'session_id' => 'nullable|string|max:100',
            'document_ids' => 'nullable|array',
            'document_ids.*' => 'integer',
        ]);

        $sessionId = $validated['session_id'] ?? ('stream-' . Str::random(16));
        $apiKey = $request->attributes->get('authenticated_api_key');

        // Human Takeover Gatekeeper: Cek apakah ada tiket aktif (open / in_progress)
        $activeTicket = ChatTicket::where('session_id', $sessionId)
            ->whereIn('status', ['open', 'in_progress'])
            ->latest('id')
            ->first();

        if ($activeTicket) {
            if ($apiKey && !$activeTicket->api_key_id) {
                $activeTicket->api_key_id = $apiKey->id;
            }
            \App\Services\EntityExtractorService::enrichTicket($activeTicket, $validated['query']);

            $senderDisplayName = $activeTicket->citizen_name ?: 'Warga';

            $msg = $activeTicket->messages()->create([
                'sender_type' => 'citizen',
                'sender_id' => null,
                'sender_name' => $senderDisplayName,
                'message' => $validated['query'],
                'is_internal_note' => false,
            ]);

            $activeTicket->last_message_at = now();
            $activeTicket->save();

            event(new TicketMessageSent($msg));
            event(new TicketUpdated($activeTicket));

            return new StreamedResponse(function () {
                $reply = 'Pesan Anda telah diteruskan langsung ke Petugas Helpdesk kami. Mohon ditunggu balasan langsung dari petugas.';
                echo "data: " . json_encode(['type' => 'chunk', 'content' => $reply], JSON_UNESCAPED_UNICODE) . "\n\n";
                echo "data: " . json_encode(['type' => 'done', 'content' => ''], JSON_UNESCAPED_UNICODE) . "\n\n";
                if (ob_get_level() > 0) ob_flush();
                flush();
            }, 200, [
                'Content-Type' => 'text/event-stream',
                'Cache-Control' => 'no-cache',
                'Connection' => 'keep-alive',
                'X-Accel-Buffering' => 'no',
            ]);
        }

        // Load active production prompt & parameters
        $systemPrompt = $this->buildFullSystemPrompt();
        $temperature = (float) AppSetting::getVal('rag_temperature', '0.2');
        $topK = (int) AppSetting::getVal('rag_top_k', '8');

        $payload = [
            'query' => $validated['query'],
            'session_id' => $sessionId,
            'system_prompt' => $systemPrompt,
            'temperature' => $temperature,
            'top_k' => $topK,
            'document_ids' => $validated['document_ids'] ?? null,
            'include_debug' => false,
        ];

        return new StreamedResponse(function () use ($payload, $validated, $sessionId, $apiKey) {
            $hasEmittedData = false;
            $ch = curl_init($this->getAiBaseUrl() . '/api/chat/stream');
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                'Authorization: Bearer ' . $this->getInternalToken(),
                'Content-Type: application/json',
                'Accept: text/event-stream',
            ]);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
            curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($ch, $data) use (&$hasEmittedData) {
                if (strlen($data) > 0) {
                    $hasEmittedData = true;
                }
                echo $data;
                if (ob_get_level() > 0) {
                    ob_flush();
                }
                flush();
                return strlen($data);
            });
            curl_setopt($ch, CURLOPT_TIMEOUT, 120);

            curl_exec($ch);
            $curlError = curl_error($ch);
            curl_close($ch);

            // The Python stream may create a handoff ticket while forwarding SSE.
            // Attach it to this public API key so staff replies reach this client.
            if ($apiKey) {
                ChatTicket::where('session_id', $sessionId)
                    ->whereIn('status', ['open', 'in_progress'])
                    ->whereNull('api_key_id')
                    ->latest('id')
                    ->limit(1)
                    ->update(['api_key_id' => $apiKey->id]);
            }

            // Jika cURL gagal dan belum ada data yang terkirim, lakukan graceful degradation stream
            if (!$hasEmittedData || $curlError) {
                Log::warning('AI Service streaming failed, fallback to local graceful degradation: ' . $curlError);
                $fallback = \App\Services\GracefulDegradationService::resolveFallback($validated['query']);
                $fallbackText = $fallback['answer'];

                echo "data: " . json_encode(['type' => 'chunk', 'content' => $fallbackText], JSON_UNESCAPED_UNICODE) . "\n\n";
                echo "data: " . json_encode(['type' => 'done', 'content' => ''], JSON_UNESCAPED_UNICODE) . "\n\n";
                if (ob_get_level() > 0) {
                    ob_flush();
                }
                flush();
            }
        }, 200, [
            'Content-Type' => 'text/event-stream',
            'Cache-Control' => 'no-cache',
            'Connection' => 'keep-alive',
            'X-Accel-Buffering' => 'no',
        ]);
    }
}
