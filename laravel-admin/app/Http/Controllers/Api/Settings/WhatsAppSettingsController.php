<?php

namespace App\Http\Controllers\Api\Settings;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use App\Services\Settings\ChannelSettingsService;
use App\Services\WhatsAppGateway;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Crypt;

class WhatsAppSettingsController extends Controller
{
    public function __construct(
        private ChannelSettingsService $settings,
        private WhatsAppGateway $gateway,
    ) {
    }

    public function getWhatsappSettings()
    {
        return response()->json($this->settings->getWhatsapp());
    }

    /**
     * Save/Update WhatsApp settings
     */
    public function updateWhatsappSettings(Request $request)
    {
        $rawApiUrl = trim($request->input('wa_api_url', ''));
        if (!empty($rawApiUrl) && !preg_match('#^https?://#i', $rawApiUrl)) {
            $rawApiUrl = 'https://' . $rawApiUrl;
        }

        $rawToken = trim($request->input('wa_token', ''));
        $rawPhone = trim($request->input('wa_phone_number', ''));
        $rawVerifyToken = trim($request->input('wa_webhook_verify_token', ''));

        $request->merge([
            'wa_api_url' => !empty($rawApiUrl) ? $rawApiUrl : null,
            'wa_token' => !empty($rawToken) ? $rawToken : null,
            'wa_phone_number' => !empty($rawPhone) ? $rawPhone : null,
            'wa_webhook_verify_token' => !empty($rawVerifyToken) ? $rawVerifyToken : null,
        ]);

        $validated = $request->validate([
            'wa_status' => 'required|boolean',
            'wa_api_url' => 'nullable|url',
            'wa_token' => 'nullable|string',
            'wa_phone_number' => 'nullable|string',
            'wa_webhook_verify_token' => 'nullable|string|max:100',
        ], [
            'wa_api_url.url' => 'URL Endpoint Gateway WhatsApp harus berupa URL yang valid (contoh: https://graph.facebook.com/... atau https://api.fonnte.com/send).',
        ]);

        $this->settings->updateWhatsapp($validated);

        return response()->json([
            'success' => true,
            'message' => 'Pengaturan WhatsApp berhasil disimpan.'
        ]);
    }

    /**
     * Test WhatsApp Gateway Connection by sending a test message
     */
    public function testWhatsappConnection(Request $request)
    {
        $validated = $request->validate([
            'target_phone' => 'required|string|min:6|max:20',
            'test_message' => 'nullable|string|max:500',
        ]);

        $apiUrl = AppSetting::getVal('wa_api_url', '');
        $encryptedToken = AppSetting::getVal('wa_token', '');

        if (empty($apiUrl) || empty($encryptedToken)) {
            return response()->json([
                'success' => false,
                'message' => 'URL API atau Access Token WhatsApp belum dikonfigurasi.',
            ], 422);
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal mendekripsi token WhatsApp yang tersimpan.',
            ], 500);
        }

        $message = $validated['test_message'] ?? "Halo! Ini adalah pesan uji coba koneksi gateway WhatsApp resmi Layanan Informasi Diskominfotik Kota Banda Aceh.";
        $to = $validated['target_phone'];

        try {
            $response = $this->gateway->send($apiUrl, $token, $to, $message);

            if ($response->successful()) {
                return response()->json([
                    'success' => true,
                    'message' => "Pesan uji coba berhasil terkirim ke {$to}.",
                    'gateway_response' => $response->json(),
                ]);
            }

            return response()->json([
                'success' => false,
                'message' => 'Gateway WhatsApp merespon dengan status ' . $response->status() . ': ' . ($response->json('error.message') ?? $response->body()),
            ], 502);
        } catch (\Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal terhubung ke URL Gateway: ' . $e->getMessage(),
            ], 500);
        }
    }
}
