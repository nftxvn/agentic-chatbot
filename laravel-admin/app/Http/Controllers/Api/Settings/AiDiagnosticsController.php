<?php

namespace App\Http\Controllers\Api\Settings;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use App\Services\Settings\OllamaModelCatalog;
use Illuminate\Http\Request;

class AiDiagnosticsController extends Controller
{
    public function __construct(private OllamaModelCatalog $catalog)
    {
    }

    public function getAvailableModels()
    {
        return response()->json($this->catalog->get($this->resolveOllamaUrl()));
    }

    /**
     * Resolve effective Ollama URL, ensuring Docker container translates localhost to host.docker.internal
     */
    private function resolveOllamaUrl(): string
    {
        $ollamaUrl = env('OLLAMA_BASE_URL', env('OLLAMA_URL', config('services.ai.ollama_url', 'http://127.0.0.1:11434')));
        if (file_exists('/.dockerenv') || env('DOCKER_CONTAINER', false)) {
            if (str_contains($ollamaUrl, 'localhost') || str_contains($ollamaUrl, '127.0.0.1')) {
                $ollamaUrl = str_replace(['localhost', '127.0.0.1'], 'host.docker.internal', $ollamaUrl);
            }
        }
        return rtrim($ollamaUrl, '/');
    }

    /**
     * GET /api/settings/hardware — Real-time GPU VRAM, System RAM & Environment Diagnostics
     */
    public function getHardwareStatus(Request $request)
    {
        $aiUrl = env('AI_SERVICE_URL', config('services.ai.url', config('services.ai_microservice.url', 'http://127.0.0.1:8080')));
        if (file_exists('/.dockerenv') || env('DOCKER_CONTAINER', false)) {
            if (str_contains($aiUrl, 'localhost') || str_contains($aiUrl, '127.0.0.1')) {
                $aiUrl = str_replace(['localhost', '127.0.0.1'], 'python-ai', $aiUrl);
            }
        }
        $token = (string) (env('AI_SERVICE_TOKEN', config('services.ai.token', config('services.ai_microservice.token', env('INTERNAL_API_TOKEN', 'dev-internal-token-secret-1234567890')))));
        $model = $request->query('model');

        try {
            $response = \Illuminate\Support\Facades\Http::withHeaders([
                'Authorization' => "Bearer {$token}",
            ])->timeout(5)->get("{$aiUrl}/api/health/hardware", [
                'nocache' => 1,
                'model' => $model,
            ]);

            if ($response->successful()) {
                return response()->json([
                    'success' => true,
                    'data' => $response->json(),
                ]);
            }
        } catch (\Exception $e) {
            // AI service unavailable
        }

        return response()->json([
            'success' => false,
            'message' => 'Layanan Python AI tidak dapat dihubungi untuk membaca diagnostik hardware.',
        ], 503);
    }

    /**
     * POST /api/settings/models/benchmark — Test live inference speed (tok/s) on selected model
     */
    public function benchmarkModel(Request $request)
    {
        $request->validate([
            'model' => 'nullable|string|max:100',
        ]);

        $ollamaUrl = $this->resolveOllamaUrl();
        $model = $request->input('model') ?: AppSetting::getVal('llm_model_name', 'qwen2.5:7b');

        try {
            $startTime = microtime(true);
            $response = \Illuminate\Support\Facades\Http::timeout(60)->post("{$ollamaUrl}/api/generate", [
                'model' => $model,
                'prompt' => 'Sebutkan 3 prinsip utama pelayanan informasi publik bagi aparatur sipil negara dalam 2 kalimat singkat.',
                'stream' => false,
                'options' => [
                    'temperature' => 0.1,
                    'num_predict' => 40,
                ],
            ]);

            if (!$response->successful()) {
                return response()->json([
                    'success' => false,
                    'message' => 'Ollama gagal mengeksekusi inferensi benchmark: ' . ($response->json('error') ?? $response->body()),
                ], 500);
            }

            $data = $response->json();
            $evalCount = $data['eval_count'] ?? 0;
            $evalDurationNs = $data['eval_duration'] ?? 1;
            $promptEvalDurationNs = $data['prompt_eval_duration'] ?? 0;
            $totalDurationNs = $data['total_duration'] ?? 1;

            $tokPerSec = $evalDurationNs > 0 ? round($evalCount / ($evalDurationNs / 1e9), 1) : 0;
            $ttftMs = round($promptEvalDurationNs / 1e6);
            $totalDurationMs = round((microtime(true) - $startTime) * 1000);

            return response()->json([
                'success' => true,
                'model' => $model,
                'tokens_per_second' => $tokPerSec,
                'eval_count' => $evalCount,
                'eval_duration_ms' => round($evalDurationNs / 1e6),
                'time_to_first_token_ms' => $ttftMs,
                'total_duration_ms' => $totalDurationMs,
                'sample_output' => trim($data['response'] ?? ''),
                'tested_at' => now()->translatedFormat('H:i:s, d M Y'),
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal menjalankan benchmark: ' . $e->getMessage(),
            ], 500);
        }
    }
}
