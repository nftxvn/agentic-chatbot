<?php

use App\Http\Controllers\DocumentController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
|
| Here is where you can register web routes for your application. These
| routes are loaded by the RouteServiceProvider and all of them will
| be assigned to the "web" middleware group.
|
*/

Route::get('/', function () {
    return redirect()->route('dashboard');
});

Route::middleware(['auth'])->group(function () {
    Route::get('/dashboard', [DocumentController::class, 'index'])->name('dashboard');
    Route::get('/documents/{id}', [DocumentController::class, 'show'])->name('documents.show');
    Route::post('/documents/upload', [DocumentController::class, 'upload'])->name('documents.upload');
    Route::post('/documents/{id}/replace', [DocumentController::class, 'replace'])->name('documents.replace');
    Route::delete('/documents/{id}', [DocumentController::class, 'destroy'])->name('documents.destroy');
    Route::get('/documents/{id}/pdf', [DocumentController::class, 'servePdf'])->name('documents.pdf');
});

Route::get('/login', function() {
    $user = \App\Models\User::firstOrCreate(
        ['email' => 'admin@admin.com'],
        ['name' => 'Admin', 'password' => bcrypt('password')]
    );
    \Illuminate\Support\Facades\Auth::login($user);
    return redirect()->route('dashboard');
})->name('login');

Route::post('/logout', function() {
    \Illuminate\Support\Facades\Auth::logout();
    return redirect()->route('login');
})->name('logout');
