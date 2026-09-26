<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        channels: __DIR__.'/../routes/channels.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        // Trust all upstream proxies (Cloudflare Tunnel, Vite proxy, etc.)
        $middleware->trustProxies(at: '*');

        // Sanctum SPA stateful middleware for cookie-based session auth
        $middleware->statefulApi();

        // Register route middleware aliases
        $middleware->alias([
            'auth.apikey' => \App\Http\Middleware\AuthenticateApiKey::class,
            'auth.internal' => \App\Http\Middleware\AuthenticateInternalService::class,
        ]);

        // Ensure API/SPA requests return JSON 401 for unauthenticated responses without redirection
        $middleware->redirectGuestsTo(fn (Request $request) => null);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*'),
        );
    })->create();
