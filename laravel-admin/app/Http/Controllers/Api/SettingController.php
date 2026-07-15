<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\AppSetting;
use Illuminate\Http\Request;

class SettingController extends Controller
{
    /**
     * Get all settings related to WhatsApp
     */
    public function getWhatsappSettings()
    {
        $token = AppSetting::getVal('wa_token', '');
        
        return response()->json([
            'wa_status' => AppSetting::getVal('wa_status', 'false') === 'true',
            'wa_api_url' => AppSetting::getVal('wa_api_url', ''),
            'wa_token' => $token ? '••••••••••••' : '', // mask token when fetching
            'wa_phone_number' => AppSetting::getVal('wa_phone_number', '')
        ]);
    }

    /**
     * Save/Update WhatsApp settings
     */
    public function updateWhatsappSettings(Request $request)
    {
        $validated = $request->validate([
            'wa_status' => 'required|boolean',
            'wa_api_url' => 'nullable|url',
            'wa_token' => 'nullable|string',
            'wa_phone_number' => 'nullable|string',
        ]);

        AppSetting::setVal('wa_status', $validated['wa_status'] ? 'true' : 'false');
        
        if (isset($validated['wa_api_url'])) {
            AppSetting::setVal('wa_api_url', $validated['wa_api_url']);
        }
        
        // Only update token if it's provided and not masked
        if (isset($validated['wa_token']) && $validated['wa_token'] !== '••••••••••••') {
            AppSetting::setVal('wa_token', $validated['wa_token']);
        }
        
        if (isset($validated['wa_phone_number'])) {
            AppSetting::setVal('wa_phone_number', $validated['wa_phone_number']);
        }

        return response()->json([
            'message' => 'Pengaturan WhatsApp berhasil disimpan.'
        ]);
    }
}
