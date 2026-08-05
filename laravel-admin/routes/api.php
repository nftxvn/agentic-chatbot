<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\DocumentCategoryController;
use App\Http\Controllers\Api\DocumentController;
use App\Http\Controllers\Api\ForgotPasswordController;
use App\Http\Controllers\Api\ResetPasswordController;
use App\Http\Controllers\Api\SettingController;
use App\Http\Controllers\Api\FlowchartController;
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

// ── Public auth routes ────────────────────────────────────────────────────
Route::prefix('auth')->group(function () {
    Route::post('login',          [AuthController::class, 'login'])->name('api.auth.login');
    Route::post('forgot-password',[ForgotPasswordController::class, 'sendResetLink'])->name('api.auth.forgot-password');
    Route::post('reset-password', [ResetPasswordController::class, 'reset'])->name('api.auth.reset-password');
});

// ── Protected routes (Sanctum session auth) ───────────────────────────────
Route::middleware('auth:sanctum')->group(function () {

    // Auth
    Route::prefix('auth')->group(function () {
        Route::get('user',            [AuthController::class, 'user'])->name('api.auth.user');
        Route::post('change-password',[AuthController::class, 'changePassword'])->name('api.auth.change-password');
        Route::post('logout',         [AuthController::class, 'logout'])->name('api.auth.logout');
    });

    // Categories
    Route::prefix('categories')->group(function () {
        Route::get('/',              [DocumentCategoryController::class, 'index'])->name('api.categories.index');
        Route::post('/',             [DocumentCategoryController::class, 'store'])->name('api.categories.store');
        Route::put('/{id}',          [DocumentCategoryController::class, 'update'])->name('api.categories.update');
        Route::delete('/{id}',       [DocumentCategoryController::class, 'destroy'])->name('api.categories.destroy');
    });

    // Documents
    Route::prefix('documents')->group(function () {
        Route::get('/',              [DocumentController::class, 'index'])->name('api.documents.index');
        Route::post('/',             [DocumentController::class, 'upload'])->name('api.documents.upload');
        Route::get('/{id}',          [DocumentController::class, 'show'])->name('api.documents.show');
        Route::get('/{id}/chunks',   [DocumentController::class, 'chunks'])->name('api.documents.chunks');
        Route::post('/{id}/replace', [DocumentController::class, 'replace'])->name('api.documents.replace');
        Route::post('/{id}/cancel',  [DocumentController::class, 'cancel'])->name('api.documents.cancel');
        Route::post('/{id}/resume',  [DocumentController::class, 'resume'])->name('api.documents.resume');
        Route::delete('/{id}',       [DocumentController::class, 'destroy'])->name('api.documents.destroy');
        Route::get('/{id}/pdf',      [DocumentController::class, 'servePdf'])->name('api.documents.pdf');

        // Flowchart
        Route::get('/{id}/flowchart', [FlowchartController::class, 'show'])->name('api.documents.flowchart.show');
        Route::put('/{id}/flowchart', [FlowchartController::class, 'update'])->name('api.documents.flowchart.update');
        Route::post('/{id}/flowchart/finalize', [FlowchartController::class, 'finalize'])->name('api.documents.flowchart.finalize');
    });

    // Settings
    Route::prefix('settings')->group(function () {
        Route::get('whatsapp', [SettingController::class, 'getWhatsappSettings'])->name('api.settings.whatsapp.get');
        Route::post('whatsapp', [SettingController::class, 'updateWhatsappSettings'])->name('api.settings.whatsapp.update');
    });
});
