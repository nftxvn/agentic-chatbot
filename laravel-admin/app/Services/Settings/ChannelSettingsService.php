<?php

namespace App\Services\Settings;

use App\Models\AppSetting;
use Illuminate\Support\Facades\Crypt;

class ChannelSettingsService
{
    /**
     * Get all settings related to WhatsApp
     */
    public function getWhatsapp(): array
    {
        $rawToken = AppSetting::getVal('wa_token', '');
        $hasToken = !empty($rawToken);

        return [
            'wa_status' => AppSetting::getVal('wa_status', 'false') === 'true',
            'wa_api_url' => AppSetting::getVal('wa_api_url', ''),
            'wa_token' => $hasToken ? '••••••••••••' : '', // mask token when fetching
            'wa_phone_number' => AppSetting::getVal('wa_phone_number', ''),
            'wa_webhook_verify_token' => AppSetting::getVal('wa_webhook_verify_token', 'diskominfo_wa_rag_token'),
            'webhook_url' => url('/api/v1/webhook/whatsapp'),
        ];
    }

    public function updateWhatsapp(array $validated): void
    {
        AppSetting::setVal('wa_status', $validated['wa_status'] ? 'true' : 'false');
        AppSetting::setVal('wa_api_url', $validated['wa_api_url'] ?? '');

        // Only update token if it's provided and not masked (encrypt token at rest)
        if (isset($validated['wa_token']) && $validated['wa_token'] !== '••••••••••••') {
            $valToSave = !empty($validated['wa_token']) ? Crypt::encryptString($validated['wa_token']) : '';
            AppSetting::setVal('wa_token', $valToSave);
        } elseif (is_null($validated['wa_token'])) {
            AppSetting::setVal('wa_token', '');
        }

        AppSetting::setVal('wa_phone_number', $validated['wa_phone_number'] ?? '');
        AppSetting::setVal('wa_webhook_verify_token', $validated['wa_webhook_verify_token'] ?? 'diskominfo_wa_rag_token');
    }

    /**
     * Get all settings related to Telegram
     */
    public function getTelegram(): array
    {
        $rawToken = AppSetting::getVal('telegram_bot_token', '');
        $hasToken = !empty($rawToken);
        $botUsername = AppSetting::getVal('telegram_bot_username', '');

        // Hapus username bot demo lama yang masih tersimpan di database aktif.
        if (strcasecmp(ltrim($botUsername, '@'), 'TesterDiskoBot') === 0) {
            AppSetting::setVal('telegram_bot_username', '');
            $botUsername = '';
        }

        return [
            'telegram_status' => AppSetting::getVal('telegram_status', 'false') === 'true',
            'telegram_bot_token' => $hasToken ? '••••••••••••' : '',
            'telegram_bot_username' => $botUsername,
            'webhook_url' => url('/api/v1/webhook/telegram'),
        ];
    }

    public function updateTelegram(array $validated): void
    {
        AppSetting::setVal('telegram_status', $validated['telegram_status'] ? 'true' : 'false');
        AppSetting::setVal('telegram_bot_username', $validated['telegram_bot_username'] ?? '');

        // Only update token if it's provided and not masked
        if (isset($validated['telegram_bot_token']) && $validated['telegram_bot_token'] !== '••••••••••••') {
            $valToSave = !empty($validated['telegram_bot_token']) ? Crypt::encryptString($validated['telegram_bot_token']) : '';
            AppSetting::setVal('telegram_bot_token', $valToSave);

            // Try to fetch getMe to automatically discover bot username
            if (!empty($validated['telegram_bot_token'])) {
                try {
                    $getMeRes = \Illuminate\Support\Facades\Http::timeout(5)->get("https://api.telegram.org/bot{$validated['telegram_bot_token']}/getMe");
                    if ($getMeRes->successful() && $getMeRes->json('ok')) {
                        $botUser = $getMeRes->json('result.username', '');
                        if (!empty($botUser)) {
                            AppSetting::setVal('telegram_bot_username', '@' . ltrim($botUser, '@'));
                        }
                    }
                } catch (\Exception $e) {
                    // Ignore network errors
                }
            }
        } elseif (is_null($validated['telegram_bot_token'])) {
            AppSetting::setVal('telegram_bot_token', '');
        }
    }
}
