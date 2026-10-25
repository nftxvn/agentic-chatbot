<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class AuthController extends Controller
{
    /**
     * Handle SPA login request.
     */
    public function login(Request $request): JsonResponse
    {
        $credentials = $request->validate([
            'email'    => ['required', 'email'],
            'password' => ['required', 'string'],
        ]);

        if (!Auth::attempt($credentials, $request->boolean('remember'))) {
            return response()->json([
                'success' => false,
                'message' => 'Email atau password yang Anda masukkan salah.',
            ], 401);
        }

        if ($request->hasSession()) {
            $request->session()->regenerate();
        }

        return response()->json([
            'success' => true,
            'message' => 'Login berhasil.',
            'data'    => [
                'user' => [
                    'id'    => Auth::id(),
                    'name'  => Auth::user()->name,
                    'email' => Auth::user()->email,
                ],
            ],
        ]);
    }

    /**
     * Handle SPA logout request.
     */
    public function logout(Request $request): JsonResponse
    {
        Auth::guard('web')->logout();

        if ($request->hasSession()) {
            $request->session()->invalidate();
            $request->session()->regenerateToken();
        }

        return response()->json([
            'success' => true,
            'message' => 'Logout berhasil.',
        ]);
    }

    /**
     * Return the currently authenticated user.
     */
    public function user(Request $request): JsonResponse
    {
        return response()->json([
            'success' => true,
            'data'    => [
                'user' => [
                    'id'    => $request->user()->id,
                    'name'  => $request->user()->name,
                    'email' => $request->user()->email,
                ],
            ],
        ]);
    }

    /**
     * Change user password directly without email verification link.
     */
    public function changePassword(Request $request): JsonResponse
    {
        $request->validate([
            'current_password' => ['required', 'string'],
            'new_password'     => ['required', 'string', 'min:8', 'confirmed'],
        ], [
            'current_password.required' => 'Password saat ini wajib diisi.',
            'new_password.required'     => 'Password baru wajib diisi.',
            'new_password.min'          => 'Password baru minimal 8 karakter.',
            'new_password.confirmed'    => 'Konfirmasi password baru tidak cocok.',
        ]);

        $user = $request->user();

        if (!\Illuminate\Support\Facades\Hash::check($request->input('current_password'), $user->password)) {
            return response()->json([
                'success' => false,
                'message' => 'Password saat ini yang Anda masukkan salah.',
            ], 422);
        }

        $user->update([
            'password' => \Illuminate\Support\Facades\Hash::make($request->input('new_password')),
        ]);

        return response()->json([
            'success' => true,
            'message' => 'Password berhasil diperbarui.',
        ]);
    }
}
