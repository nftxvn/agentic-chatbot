<?php

namespace App\Services;

use App\Models\AppSetting;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Log;

class WhatsAppClient
{
    public function __construct(private WhatsAppGateway $gateway)
    {
    }

    /**
     * Kirim pesan keluar ke WhatsApp Gateway
     */
    public function send(string $to, string $message): bool
    {
        $apiUrl = AppSetting::getVal('wa_api_url', '');
        $encryptedToken = AppSetting::getVal('wa_token', '');

        if (empty($apiUrl) || empty($encryptedToken)) {
            Log::warning('Tidak dapat mengirim pesan WhatsApp: URL API atau Token belum dikonfigurasi.');
            return false;
        }

        try {
            $token = Crypt::decryptString($encryptedToken);
        } catch (\Exception $e) {
            Log::error('Gagal mendekripsi WhatsApp Token: ' . $e->getMessage());
            return false;
        }

        try {
            $response = $this->gateway->send($apiUrl, $token, $to, $message);

            Log::info('Pesan WhatsApp terkirim ke gateway', [
                'recipient' => $to,
                'status' => $response->status(),
            ]);

            return $response->successful();
        } catch (\Exception $e) {
            Log::error('Gagal mengirim HTTP request ke WhatsApp Gateway: ' . $e->getMessage());
            return false;
        }
    }
}
