<?php

/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
| Laravel sekarang berfungsi sebagai pure API backend.
| Satu-satunya web route yang tersisa adalah fallback untuk React SPA
| dan endpoint reset password (karena link dikirim via email ke browser).
|
| React frontend menangani semua UI — Laravel hanya melayani JSON.
|--------------------------------------------------------------------------
*/

use Illuminate\Support\Facades\Route;

Route::get('/login', function () {
    return response()->json(['message' => 'Unauthenticated.'], 401);
})->name('login');

// Reset password route — tetap di web karena link dikirim via email ke browser
// React SPA akan menangani form-nya, tapi token dikirim ke API
Route::get('/reset-password/{token}', function () {
    // Redirect ke React frontend dengan token yang sama
    $frontendUrl = config('app.frontend_url', 'http://localhost:5173');
    $token = request()->route('token');
    $email = request()->query('email', '');
    return redirect("{$frontendUrl}/reset-password?token={$token}&email={$email}");
})->name('password.reset');

// File & Image streaming routes with session cookie auth for direct browser tabs/windows
use App\Http\Controllers\Api\DocumentController;
use App\Http\Controllers\Api\EkstraksiController;

Route::middleware('auth:sanctum,web')->prefix('api/documents')->group(function () {
    Route::get('/{id}/pdf', [DocumentController::class, 'servePdf'])->name('api.documents.pdf');
    Route::get('/{id}/halaman/{pageNumber}/citra', [EkstraksiController::class, 'citraHalaman'])->name('api.documents.halaman.citra');
});
