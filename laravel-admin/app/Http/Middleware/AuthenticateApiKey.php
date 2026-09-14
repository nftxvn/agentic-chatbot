<?php

namespace App\Http\Middleware;

use App\Models\ApiKey;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class AuthenticateApiKey
{
    /**
     * Handle an incoming request by verifying the Bearer API token or X-API-Key header.
     */
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken() ?: $request->header('X-API-Key');

        if (!$token) {
            return response()->json([
                'success' => false,
                'message' => 'Autentikasi gagal: API Key tidak ditemukan pada header Authorization (Bearer) atau X-API-Key.',
            ], 401);
        }

        $apiKey = ApiKey::where('key', $token)->first();

        if (!$apiKey || !$apiKey->is_active) {
            return response()->json([
                'success' => false,
                'message' => 'Autentikasi gagal: API Key tidak valid atau telah dinonaktifkan.',
            ], 401);
        }

        // Update last_used_at timestamp silently
        $apiKey->timestamps = false;
        $apiKey->last_used_at = now();
        $apiKey->save();
        $apiKey->timestamps = true;

        // Attach authenticated key model to request attributes
        $request->attributes->set('authenticated_api_key', $apiKey);

        return $next($request);
    }
}
