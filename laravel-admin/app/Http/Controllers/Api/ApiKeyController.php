<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ApiKey;
use Illuminate\Support\Str;
use Illuminate\Http\Request;

class ApiKeyController extends Controller
{
    /**
     * List all API keys
     */
    public function index()
    {
        $keys = ApiKey::with('latestWebhookDelivery')->orderBy('created_at', 'desc')->get()->map(function ($key) {
            return [
                'id' => $key->id,
                'name' => $key->name,
                'masked_key' => $key->masked_key,
                'is_active' => $key->is_active,
                'last_used_at' => $key->last_used_at?->toISOString(),
                'created_at' => $key->created_at->toISOString(),
                'webhook_url' => $key->webhook_url,
                'webhook_enabled' => $key->webhook_enabled,
                'webhook_secret_configured' => !empty($key->webhook_secret),
                'last_webhook_delivery' => $key->latestWebhookDelivery ? [
                    'status' => $key->latestWebhookDelivery->status,
                    'attempts' => $key->latestWebhookDelivery->attempts,
                    'response_status' => $key->latestWebhookDelivery->response_status,
                    'last_error' => $key->latestWebhookDelivery->last_error,
                    'delivered_at' => $key->latestWebhookDelivery->delivered_at?->toISOString(),
                    'created_at' => $key->latestWebhookDelivery->created_at?->toISOString(),
                ] : null,
            ];
        });

        return response()->json([
            'success' => true,
            'data' => $keys,
        ]);
    }

    /**
     * Generate a new API key
     */
    public function store(Request $request)
    {
        $validated = $request->validate([
            'name' => 'required|string|max:100',
        ]);

        $plainKey = ApiKey::generateSecretKey();

        $apiKey = ApiKey::create([
            'name' => $validated['name'],
            'key' => $plainKey,
            'is_active' => true,
        ]);

        return response()->json([
            'success' => true,
            'message' => 'API Key berhasil dibuat.',
            'data' => [
                'id' => $apiKey->id,
                'name' => $apiKey->name,
                'plain_key' => $plainKey, // Returned only once upon creation
                'masked_key' => $apiKey->masked_key,
                'is_active' => $apiKey->is_active,
                'created_at' => $apiKey->created_at->toISOString(),
            ],
        ], 201);
    }

    /**
     * Toggle active status
     */
    public function toggle($id)
    {
        $apiKey = ApiKey::findOrFail($id);
        $apiKey->is_active = !$apiKey->is_active;
        $apiKey->save();

        return response()->json([
            'success' => true,
            'message' => 'Status API Key berhasil diperbarui.',
            'data' => [
                'id' => $apiKey->id,
                'is_active' => $apiKey->is_active,
            ],
        ]);
    }

    /**
     * Delete/Revoke API key
     */
    public function destroy($id)
    {
        $apiKey = ApiKey::findOrFail($id);
        $apiKey->delete();

        return response()->json([
            'success' => true,
            'message' => 'API Key berhasil dicabut dan dihapus permanen.',
        ]);
    }

    public function updateWebhook(Request $request, int $id)
    {
        $apiKey = ApiKey::findOrFail($id);
        $validated = $request->validate([
            'webhook_url' => 'nullable|string|max:2048',
            'webhook_enabled' => 'required|boolean',
        ]);

        $url = trim($validated['webhook_url'] ?? '');
        if ($url !== '') {
            $parts = parse_url($url);
            if (!$parts || !in_array(strtolower($parts['scheme'] ?? ''), ['http', 'https'], true) || empty($parts['host'])) {
                return response()->json(['success' => false, 'message' => 'URL webhook harus menggunakan HTTP atau HTTPS yang valid.'], 422);
            }

            if (strtolower($parts['scheme']) !== 'https' && !app()->environment(['local', 'testing'])) {
                return response()->json(['success' => false, 'message' => 'Webhook wajib menggunakan HTTPS di luar lingkungan lokal.'], 422);
            }
        }

        if ($validated['webhook_enabled'] && ($url === '' || empty($apiKey->webhook_secret))) {
            return response()->json(['success' => false, 'message' => 'Isi URL dan buat secret webhook sebelum mengaktifkannya.'], 422);
        }

        $apiKey->webhook_url = $url ?: null;
        $apiKey->webhook_enabled = (bool) $validated['webhook_enabled'];
        $apiKey->save();

        return response()->json([
            'success' => true,
            'message' => 'Konfigurasi webhook berhasil disimpan.',
            'data' => [
                'id' => $apiKey->id,
                'webhook_url' => $apiKey->webhook_url,
                'webhook_enabled' => $apiKey->webhook_enabled,
                'webhook_secret_configured' => !empty($apiKey->webhook_secret),
            ],
        ]);
    }

    public function rotateWebhookSecret(int $id)
    {
        $apiKey = ApiKey::findOrFail($id);
        $secret = 'sapa_whsec_' . Str::random(48);
        $apiKey->webhook_secret = $secret;
        $apiKey->save();

        return response()->json([
            'success' => true,
            'message' => 'Secret webhook dibuat. Simpan sekarang karena hanya ditampilkan satu kali.',
            'data' => ['plain_secret' => $secret],
        ]);
    }

    public function webhookDeliveries(int $id)
    {
        $apiKey = ApiKey::findOrFail($id);
        return response()->json([
            'success' => true,
            'data' => $apiKey->webhookDeliveries()->latest()->limit(20)->get([
                'id', 'event_id', 'event_type', 'status', 'attempts', 'response_status',
                'last_error', 'delivered_at', 'created_at',
            ]),
        ]);
    }
}
