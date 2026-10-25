<?php

namespace App\Services\Settings;

use App\Models\AppSetting;

class OllamaModelCatalog
{
    /**
     * Get list of all installed LLM models from Ollama with capacity recommendations
     */
    public function get(string $ollamaUrl): array
    {
        $models = [];
        $activeModel = AppSetting::getVal('llm_model_name', 'qwen2.5:7b');

        try {
            $response = \Illuminate\Support\Facades\Http::timeout(4)->get("{$ollamaUrl}/api/tags");
            if ($response->successful() && isset($response->json()['models'])) {
                $rawModels = $response->json()['models'];
                foreach ($rawModels as $m) {
                    $name = $m['name'] ?? '';
                    if (empty($name)) continue;

                    $sizeBytes = $m['size'] ?? 0;
                    $sizeGb = round($sizeBytes / (1024 * 1024 * 1024), 2);
                    $nameLower = strtolower($name);

                    // Skip vision-only or embedding models if clearly marked
                    $isVision = str_contains($nameLower, 'vl') || str_contains($nameLower, 'vision');
                    $isEmbedding = str_contains($nameLower, 'bge') || str_contains($nameLower, 'embed');

                    // Classification & recommendation based on parameter size
                    $tier = 'medium';
                    $badge = 'Sedang (Kualitas Tinggi, 1–2 User)';
                    $speed = '15–25 tok/s';
                    $vramEst = '~4.5–5.5 GB';
                    $tagColor = 'amber';

                    if (str_contains($nameLower, '0.5b') || str_contains($nameLower, '1.5b') || str_contains($nameLower, '1b') || str_contains($nameLower, '3b') || str_contains($nameLower, '2b')) {
                        $tier = 'light';
                        $badge = 'Sangat Ringan (Rekomendasi 3–5 User Bersamaan)';
                        $speed = '45–60 tok/s';
                        $vramEst = '~2.0–2.5 GB';
                        $tagColor = 'emerald';
                    } elseif (str_contains($nameLower, '14b') || str_contains($nameLower, '32b') || str_contains($nameLower, '70b') || $sizeGb > 9.0) {
                        $tier = 'heavy';
                        $badge = 'Sangat Berat (Butuh Server Khusus / GPU Besar)';
                        $speed = '3–8 tok/s';
                        $vramEst = '>10 GB';
                        $tagColor = 'rose';
                    } elseif ($isVision) {
                        $tier = 'specialized';
                        $badge = 'Model Vision (OCR / Dokumen Gambar)';
                        $speed = '10–20 tok/s';
                        $vramEst = '~6.0 GB';
                        $tagColor = 'indigo';
                    }

                    $models[] = [
                        'name' => $name,
                        'size_gb' => $sizeGb,
                        'tier' => $tier,
                        'badge' => $badge,
                        'speed' => $speed,
                        'vram_estimate' => $vramEst,
                        'tag_color' => $tagColor,
                        'is_active' => $name === $activeModel,
                        'is_vision' => $isVision,
                        'is_embedding' => $isEmbedding,
                    ];
                }
            }
        } catch (\Exception $e) {
            // Ollama offline or error
        }

        // Fallback default list if Ollama is offline or returned empty
        if (empty($models)) {
            $models = [
                [
                    'name' => 'qwen2.5:3b',
                    'size_gb' => 1.9,
                    'tier' => 'light',
                    'badge' => 'Sangat Ringan (Rekomendasi 3–5 User Bersamaan)',
                    'speed' => '45–60 tok/s',
                    'vram_estimate' => '~2.0–2.5 GB',
                    'tag_color' => 'emerald',
                    'is_active' => 'qwen2.5:3b' === $activeModel,
                    'is_vision' => false,
                    'is_embedding' => false,
                ],
                [
                    'name' => 'qwen3:8b',
                    'size_gb' => 5.2,
                    'tier' => 'medium',
                    'badge' => 'Sedang (Kualitas Tinggi, 1–2 User)',
                    'speed' => '15–25 tok/s',
                    'vram_estimate' => '~5.5 GB',
                    'tag_color' => 'amber',
                    'is_active' => 'qwen3:8b' === $activeModel,
                    'is_vision' => false,
                    'is_embedding' => false,
                ],
            ];
        }

        return [
            'active_model' => $activeModel,
            'models' => $models,
        ];
    }
}
