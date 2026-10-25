<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\DocumentCategoryController;
use App\Http\Controllers\Api\DocumentController;
use App\Http\Controllers\Api\EkstraksiController;
use App\Http\Controllers\Api\ForgotPasswordController;
use App\Http\Controllers\Api\InternalTicketController;
use App\Http\Controllers\Api\ResetPasswordController;
use App\Http\Controllers\Api\Settings\AiDiagnosticsController;
use App\Http\Controllers\Api\Settings\ChatbotSettingsController;
use App\Http\Controllers\Api\Settings\TelegramSettingsController;
use App\Http\Controllers\Api\Settings\WhatsAppSettingsController;
use App\Http\Controllers\Api\TicketController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| API Routes
|--------------------------------------------------------------------------
| Prefix  : /api
| Auth    : Laravel Sanctum (SPA cookie-based session auth)
| CSRF    : GET /sanctum/csrf-cookie  (call before login from React)
|--------------------------------------------------------------------------
*/

// ── Public auth routes (with rate limiting / brute-force protection) ───────
Route::prefix('auth')->group(function () {
    Route::post('login',           [AuthController::class, 'login'])->middleware('throttle:20,1')->name('api.auth.login');
    Route::post('forgot-password', [ForgotPasswordController::class, 'sendResetLink'])->middleware('throttle:10,1')->name('api.auth.forgot-password');
    Route::post('reset-password',  [ResetPasswordController::class, 'reset'])->middleware('throttle:10,1')->name('api.auth.reset-password');
});

// ── Protected routes (Sanctum session auth) ───────────────────────────────
Route::middleware('auth:sanctum')->group(function () {

    // Auth
    Route::prefix('auth')->group(function () {
        Route::get('user',             [AuthController::class, 'user'])->name('api.auth.user');
        Route::post('change-password', [AuthController::class, 'changePassword'])->name('api.auth.change-password');
        Route::post('logout',          [AuthController::class, 'logout'])->name('api.auth.logout');
    });

    // Categories
    Route::prefix('categories')->group(function () {
        Route::get('/',               [DocumentCategoryController::class, 'index'])->name('api.categories.index');
        Route::post('/',              [DocumentCategoryController::class, 'store'])->name('api.categories.store');
        Route::put('/{id}',           [DocumentCategoryController::class, 'update'])->name('api.categories.update');
        Route::delete('/{id}',        [DocumentCategoryController::class, 'destroy'])->name('api.categories.destroy');
    });

    // Documents
    Route::prefix('documents')->group(function () {
        Route::get('/',               [DocumentController::class, 'index'])->name('api.documents.index');
        Route::post('/',              [DocumentController::class, 'upload'])->name('api.documents.upload');
        Route::get('/{id}',           [DocumentController::class, 'show'])->name('api.documents.show');
        Route::get('/{id}/chunks',    [DocumentController::class, 'chunks'])->name('api.documents.chunks');
        Route::post('/{id}/replace',  [DocumentController::class, 'replace'])->name('api.documents.replace');
        Route::post('/{id}/cancel',   [DocumentController::class, 'cancel'])->name('api.documents.cancel');
        Route::post('/{id}/resume',   [DocumentController::class, 'resume'])->name('api.documents.resume');
        Route::delete('/{id}',        [DocumentController::class, 'destroy'])->name('api.documents.destroy');

        // Staged Extraction & Manual Correction (Python-AI sync)
        Route::post('/{id}/extraction',                   [EkstraksiController::class, 'mulai'])->name('api.documents.extraction.start');
        Route::post('/{id}/extraction/pause',             [EkstraksiController::class, 'jeda'])->name('api.documents.extraction.pause');
        Route::get('/{id}/extraction',                    [EkstraksiController::class, 'status'])->name('api.documents.extraction.status');
        Route::get('/{id}/pages',                         [EkstraksiController::class, 'halaman'])->name('api.documents.pages.index');
        Route::put('/{id}/pages/{pageNumber}',            [EkstraksiController::class, 'simpanHalaman'])->name('api.documents.pages.update');
        Route::get('/{id}/pages/dimensions',              [EkstraksiController::class, 'ukuranHalaman'])->name('api.documents.pages.dimensions');
        Route::match(['get', 'post'], '/{id}/chunks/preview', [EkstraksiController::class, 'potongan'])->name('api.documents.chunks.preview');
        Route::post('/{id}/embed',                        [EkstraksiController::class, 'simpanKorpus'])->name('api.documents.embed');
    });

    // API Key Management (Admin)
    Route::prefix('api-keys')->group(function () {
        Route::get('/',              [\App\Http\Controllers\Api\ApiKeyController::class, 'index'])->name('api.api-keys.index');
        Route::post('/',             [\App\Http\Controllers\Api\ApiKeyController::class, 'store'])->name('api.api-keys.store');
        Route::patch('/{id}/toggle', [\App\Http\Controllers\Api\ApiKeyController::class, 'toggle'])->name('api.api-keys.toggle');
        Route::patch('/{id}/webhook', [\App\Http\Controllers\Api\ApiKeyController::class, 'updateWebhook'])->name('api.api-keys.webhook.update');
        Route::post('/{id}/webhook-secret', [\App\Http\Controllers\Api\ApiKeyController::class, 'rotateWebhookSecret'])->name('api.api-keys.webhook.secret');
        Route::get('/{id}/webhook-deliveries', [\App\Http\Controllers\Api\ApiKeyController::class, 'webhookDeliveries'])->name('api.api-keys.webhook.deliveries');
        Route::delete('/{id}',       [\App\Http\Controllers\Api\ApiKeyController::class, 'destroy'])->name('api.api-keys.destroy');
    });

    // Chat Logs & Audit Trail (Admin)
    Route::prefix('chat-logs')->group(function () {
        Route::get('/',              [\App\Http\Controllers\Api\ChatLogController::class, 'index'])->name('api.chat-logs.index');
        Route::get('/analytics',     [\App\Http\Controllers\Api\ChatLogController::class, 'analytics'])->name('api.chat-logs.analytics');
        Route::delete('/purge',      [\App\Http\Controllers\Api\ChatLogController::class, 'purge'])->name('api.chat-logs.purge');
        Route::delete('/{id}',       [\App\Http\Controllers\Api\ChatLogController::class, 'destroy'])->name('api.chat-logs.destroy');
    });

    // Fast-Path & Dynamic FAQ Management
    Route::prefix('fast-paths')->group(function () {
        Route::get('/',              [\App\Http\Controllers\Api\FastPathController::class, 'index'])->name('api.fast-paths.index');
        Route::post('/',             [\App\Http\Controllers\Api\FastPathController::class, 'store'])->name('api.fast-paths.store');
        Route::get('/{id}',          [\App\Http\Controllers\Api\FastPathController::class, 'show'])->name('api.fast-paths.show');
        Route::put('/{id}',          [\App\Http\Controllers\Api\FastPathController::class, 'update'])->name('api.fast-paths.update');
        Route::patch('/{id}/toggle', [\App\Http\Controllers\Api\FastPathController::class, 'toggle'])->name('api.fast-paths.toggle');
        Route::delete('/{id}',       [\App\Http\Controllers\Api\FastPathController::class, 'destroy'])->name('api.fast-paths.destroy');
    });

    // Departmental Directory Management
    Route::prefix('directories')->group(function () {
        Route::get('/',              [\App\Http\Controllers\Api\DirectoryController::class, 'index'])->name('api.directories.index');
        Route::post('/',             [\App\Http\Controllers\Api\DirectoryController::class, 'store'])->name('api.directories.store');
        Route::get('/{id}',          [\App\Http\Controllers\Api\DirectoryController::class, 'show'])->name('api.directories.show');
        Route::put('/{id}',          [\App\Http\Controllers\Api\DirectoryController::class, 'update'])->name('api.directories.update');
        Route::patch('/{id}/toggle', [\App\Http\Controllers\Api\DirectoryController::class, 'toggle'])->name('api.directories.toggle');
        Route::delete('/{id}',       [\App\Http\Controllers\Api\DirectoryController::class, 'destroy'])->name('api.directories.destroy');
    });

    // Settings
    Route::prefix('settings')->group(function () {
        Route::get('whatsapp',            [WhatsAppSettingsController::class, 'getWhatsappSettings'])->name('api.settings.whatsapp.get');
        Route::post('whatsapp',           [WhatsAppSettingsController::class, 'updateWhatsappSettings'])->name('api.settings.whatsapp.update');
        Route::post('whatsapp/test',      [WhatsAppSettingsController::class, 'testWhatsappConnection'])->name('api.settings.whatsapp.test');
        Route::get('telegram',            [TelegramSettingsController::class, 'getTelegramSettings'])->name('api.settings.telegram.get');
        Route::post('telegram',           [TelegramSettingsController::class, 'updateTelegramSettings'])->name('api.settings.telegram.update');
        Route::post('telegram/test',      [TelegramSettingsController::class, 'testTelegramConnection'])->name('api.settings.telegram.test');
        Route::post('telegram/webhook',   [TelegramSettingsController::class, 'setTelegramWebhook'])->name('api.settings.telegram.webhook');
        Route::get('chatbot',             [ChatbotSettingsController::class, 'getChatbotSettings'])->name('api.settings.chatbot.get');
        Route::post('chatbot',            [ChatbotSettingsController::class, 'updateChatbotSettings'])->name('api.settings.chatbot.update');
        Route::post('chatbot/reset',      [ChatbotSettingsController::class, 'resetChatbotSettings'])->name('api.settings.chatbot.reset');
        Route::get('hardware',            [AiDiagnosticsController::class, 'getHardwareStatus'])->name('api.settings.hardware.get');
        Route::get('models',              [AiDiagnosticsController::class, 'getAvailableModels'])->name('api.settings.models.get');
        Route::post('models/benchmark',   [AiDiagnosticsController::class, 'benchmarkModel'])->name('api.settings.models.benchmark');
    });

    // Live Chat & Helpdesk Tickets (Admin)
    Route::prefix('tickets')->group(function () {
        Route::get('/',               [TicketController::class, 'index'])->name('api.tickets.index');
        Route::get('/stats',          [TicketController::class, 'stats'])->name('api.tickets.stats');
        Route::post('/bulk-delete',   [TicketController::class, 'bulkDestroy'])->name('api.tickets.bulk-destroy');
        Route::get('/{id}',           [TicketController::class, 'show'])->name('api.tickets.show');
        Route::post('/{id}/assign',   [TicketController::class, 'assign'])->name('api.tickets.assign');
        Route::patch('/{id}/status',  [TicketController::class, 'updateStatus'])->name('api.tickets.status');
        Route::delete('/{id}',        [TicketController::class, 'destroy'])->name('api.tickets.destroy');
        Route::get('/{id}/messages',  [TicketController::class, 'messages'])->name('api.tickets.messages');
        Route::post('/{id}/messages', [TicketController::class, 'reply'])->name('api.tickets.reply');
        Route::get('/{id}/attachments/{filename}', [TicketController::class, 'downloadAttachment'])->name('api.tickets.attachments.show');
    });
});

// ── Public Inbound Webhooks (WhatsApp & Telegram) ─────────────────────────
Route::prefix('v1/webhook')->group(function () {
    Route::get('whatsapp',  [\App\Http\Controllers\Api\V1\WhatsAppWebhookController::class, 'verify'])->name('api.v1.webhook.whatsapp.verify');
    Route::post('whatsapp', [\App\Http\Controllers\Api\V1\WhatsAppWebhookController::class, 'handle'])->name('api.v1.webhook.whatsapp.handle');
    Route::post('telegram', [\App\Http\Controllers\Api\V1\TelegramWebhookController::class, 'handle'])->name('api.v1.webhook.telegram.handle');
});

// ── Public V1 RAG API Gateway (Protected via API Key Bearer / Header) ─────
Route::prefix('v1')->middleware('auth.apikey')->group(function () {
    Route::post('chat',        [\App\Http\Controllers\Api\V1\ChatController::class, 'message'])->name('api.v1.chat.message');
    Route::post('chat/stream', [\App\Http\Controllers\Api\V1\ChatController::class, 'stream'])->name('api.v1.chat.stream');
});

// ── Internal Service Gateway (Python AI Handoff Dispatch) ─────────────────
Route::prefix('v1/internal')->middleware('auth.internal')->group(function () {
    Route::post('chat-tickets', [InternalTicketController::class, 'storeOrUpdate'])->name('api.v1.internal.chat-tickets');
    Route::post('tickets',      [InternalTicketController::class, 'storeOrUpdate'])->name('api.v1.internal.tickets');
});


