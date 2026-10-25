<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'token' => env('POSTMARK_TOKEN'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'resend' => [
        'key' => env('RESEND_KEY'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    /*
    |--------------------------------------------------------------------------
    | AI Microservice (Python)
    |--------------------------------------------------------------------------
    |
    | Configuration for the Agentic AI document processing microservice.
    | The service handles PDF parsing, OCR, chunking, and embedding generation.
    |
    */
    'ai_microservice' => [
        'url' => env('AI_SERVICE_URL', 'http://127.0.0.1:8080'),
        'token' => env('AI_SERVICE_TOKEN', env('INTERNAL_API_TOKEN', 'dev-internal-token-secret-1234567890')),
    ],

    'ai' => [
        'url' => env('AI_SERVICE_URL', 'http://127.0.0.1:8080'),
        'token' => env('AI_SERVICE_TOKEN', env('INTERNAL_API_TOKEN', 'dev-internal-token-secret-1234567890')),
        'ollama_url' => env('OLLAMA_BASE_URL', env('OLLAMA_URL', 'http://127.0.0.1:11434')),
    ],

];
