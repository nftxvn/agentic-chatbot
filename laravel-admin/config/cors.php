<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Cross-Origin Resource Sharing (CORS) Configuration
    |--------------------------------------------------------------------------
    |
    | Mengizinkan React admin-frontend (localhost:5173) dan react-widget
    | (localhost:3000) untuk berkomunikasi dengan Laravel API.
    |
    | Di production, ganti allowed_origins dengan domain frontend yang sebenarnya.
    |
    */

    'paths' => ['api/*', 'sanctum/csrf-cookie'],

    'allowed_methods' => ['*'],

    'allowed_origins' => explode(',', env('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:3000,http://192.168.137.1:5173,http://127.0.0.1:5173')),

    'allowed_origins_patterns' => [
        '#^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$#',
        '#^https://.*\.trycloudflare\.com$#',
    ],

    'allowed_headers' => ['*'],

    'exposed_headers' => [],

    'max_age' => 0,

    /*
     * supports_credentials HARUS true agar cookie Sanctum (session) bisa
     * dikirim dari React SPA ke Laravel API lintas port.
     */
    'supports_credentials' => true,

];
