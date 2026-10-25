<?php

namespace App\Services\Channels;

use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

class AiChatGateway
{
    public function postMessage(string $url, string $token, array $payload): Response
    {
        return Http::withHeaders([
            'Authorization' => 'Bearer ' . $token,
            'Content-Type' => 'application/json',
        ])->timeout(60)->post($url, $payload);
    }

    /** Forward raw SSE bytes; the caller owns event parsing and fallback policy. */
    public function stream(string $url, string $token, array $payload, callable $onChunk): string
    {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Authorization: Bearer ' . $token,
            'Content-Type: application/json',
            'Accept: text/event-stream',
        ]);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 120);
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, $onChunk);
        curl_exec($ch);
        $error = curl_error($ch);
        curl_close($ch);

        return $error;
    }
}
