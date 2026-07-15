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

// Reset password route — tetap di web karena link dikirim via email ke browser
// React SPA akan menangani form-nya, tapi token dikirim ke API
Route::get('/reset-password/{token}', function () {
    // Redirect ke React frontend dengan token yang sama
    $frontendUrl = config('app.frontend_url', 'http://localhost:5173');
    $token = request()->route('token');
    $email = request()->query('email', '');
    return redirect("{$frontendUrl}/reset-password?token={$token}&email={$email}");
})->name('password.reset');
