<?php

namespace App\Services;

use App\Services\Ai\DocumentRequests;
use App\Services\Ai\StagedExtractionRequests;

/**
 * Titik masuk kompatibel untuk request dokumen ke Python AI.
 *
 * Trait membagi operasi; konfigurasi dan pemformatan error tetap dimiliki kelas ini.
 * Setiap operasi mempertahankan timeout, payload, logging, dan fallback sendiri.
 */
class AiMicroserviceClient
{
    use DocumentRequests;
    use StagedExtractionRequests;

    /**
     * Base URL of the AI microservice.
     */
    protected string $baseUrl;

    /**
     * Bearer token for authentication.
     */
    protected string $token;

    /**
     * Create a new AiMicroserviceClient instance.
     */
    public function __construct()
    {
        $this->baseUrl = rtrim(config('services.ai_microservice.url', 'http://localhost:8080'), '/');
        $this->token = config('services.ai_microservice.token', '');
    }

    /**
     * Safely format error message from HTTP response (handles string, array, or null).
     */
    protected function extractErrorMessage($response, string $fallback = 'Terjadi kesalahan pada AI service'): string
    {
        $detail = $response->json('detail');
        if (is_string($detail) && trim($detail) !== '') {
            return $detail;
        }
        if (is_array($detail)) {
            $messages = [];
            foreach ($detail as $err) {
                if (is_array($err) && isset($err['msg'])) {
                    $field = isset($err['loc']) ? implode('.', (array)$err['loc']) . ': ' : '';
                    $messages[] = $field . $err['msg'];
                } else if (is_string($err)) {
                    $messages[] = $err;
                }
            }
            if (!empty($messages)) {
                return implode(', ', $messages);
            }
            return json_encode($detail, JSON_UNESCAPED_UNICODE);
        }
        return $fallback . ' (HTTP ' . $response->status() . ')';
    }
}
