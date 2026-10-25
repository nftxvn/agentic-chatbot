<?php

namespace App\Services;

use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

class WhatsAppGateway
{
    /** Send the existing Meta or generic gateway payload without interpreting the response. */
    public function send(string $apiUrl, string $token, string $to, string $message): Response
    {
        // Deteksi format payload berdasarkan tipe API Gateway
        if (str_contains($apiUrl, 'graph.facebook.com')) {
            // Meta Cloud API Format
            $payload = [
                'messaging_product' => 'whatsapp',
                'recipient_type' => 'individual',
                'to' => preg_replace('/[^0-9]/', '', $to),
                'type' => 'text',
                'text' => ['preview_url' => false, 'body' => $message],
            ];

            $response = Http::withHeaders([
                'Authorization' => 'Bearer ' . $token,
                'Content-Type' => 'application/json',
            ])->timeout(15)->post($apiUrl, $payload);
        } else {
            // Generic Gateway (Fonnte / Wablas / Custom Gateway)
            $payload = [
                'target' => $to,
                'phone' => $to,
                'message' => $message,
            ];

            $response = Http::withHeaders([
                'Authorization' => $token,
                'Content-Type' => 'application/json',
            ])->timeout(15)->post($apiUrl, $payload);
        }

        return $response;
    }
}
