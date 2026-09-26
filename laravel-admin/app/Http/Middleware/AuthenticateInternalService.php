<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class AuthenticateInternalService
{
    /**
     * Handle an incoming request from internal microservices (e.g. Python AI service).
     */
    public function handle(Request $request, Closure $next): Response
    {
        $token = $request->bearerToken()
            ?: $request->header('X-Internal-Token')
            ?: $request->header('X-AI-Service-Token');

        $expectedToken = config('services.ai_microservice.token')
            ?: env('INTERNAL_API_TOKEN', 'dev-internal-token-secret-1234567890');

        if (!$token || !hash_equals((string) $expectedToken, (string) $token)) {
            return response()->json([
                'success' => false,
                'message' => 'Unauthorized: Invalid internal service token.',
            ], 401);
        }

        $request->attributes->set('is_internal_service', true);

        return $next($request);
    }
}
