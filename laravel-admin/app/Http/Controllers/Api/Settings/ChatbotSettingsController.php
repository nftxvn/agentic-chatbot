<?php

namespace App\Http\Controllers\Api\Settings;

use App\Http\Controllers\Controller;
use App\Services\Settings\ChatbotSettingsService;
use Illuminate\Http\Request;

class ChatbotSettingsController extends Controller
{
    public function __construct(private ChatbotSettingsService $settings)
    {
    }

    public function getChatbotSettings()
    {
        return response()->json($this->settings->get());
    }

    public function updateChatbotSettings(Request $request)
    {
        $validated = $request->validate([
            'llm_model_name' => 'nullable|string|max:100',
            'chatbot_name' => 'required|string|max:100',
            'chatbot_persona' => 'required|string|max:255',
            'rag_system_prompt' => 'required|string',
            'rag_temperature' => 'required|numeric|min:0|max:1',
            'rag_top_k' => 'required|integer|min:1|max:30',
            'rag_num_ctx' => 'nullable|integer|min:1024|max:65536',
            'chatbot_greeting' => 'nullable|string|max:500',
            'chatbot_fallback_message' => 'nullable|string|max:500',
            'rag_citation_enabled' => 'required|boolean',
        ]);

        $this->settings->update($validated);

        return response()->json([
            'message' => 'Pengaturan Chatbot & Prompt RAG berhasil disimpan.',
            'settings' => $this->settings->get(),
        ]);
    }

    public function resetChatbotSettings()
    {
        $this->settings->reset();

        return response()->json([
            'message' => 'Pengaturan Chatbot berhasil dikembalikan ke standar awal.',
            'settings' => $this->settings->get(),
        ]);
    }
}
