<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ApiKey;
use Illuminate\Http\Request;

class ApiKeyController extends Controller
{
    /**
     * List all API keys
     */
    public function index()
    {
        $keys = ApiKey::orderBy('created_at', 'desc')->get()->map(function ($key) {
            return [
                'id' => $key->id,
                'name' => $key->name,
                'masked_key' => $key->masked_key,
                'is_active' => $key->is_active,
                'last_used_at' => $key->last_used_at?->toISOString(),
                'created_at' => $key->created_at->toISOString(),
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
}
