<!DOCTYPE html>
<html lang="id" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Reset Password — Agentic IT Support Copilot Admin">
    <title>Reset Password — Agentic Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            400: '#818cf8', 500: '#6366f1',
                            600: '#4f46e5', 700: '#4338ca',
                        },
                        surface: { 800: '#1e1e2e', 900: '#11111b', 950: '#0a0a14' }
                    },
                    fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] }
                }
            }
        }
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        .glass {
            background: rgba(30, 30, 46, 0.75);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fadeInUp 0.5s ease-out both; }
    </style>
</head>
<body class="bg-surface-950 text-gray-200 font-sans antialiased min-h-screen flex items-center justify-center relative overflow-hidden">

    <div class="absolute top-[-20%] left-[-10%] w-[55%] h-[55%] rounded-full bg-brand-600/20 blur-[130px] pointer-events-none"></div>
    <div class="absolute bottom-[-20%] right-[-10%] w-[55%] h-[55%] rounded-full bg-indigo-700/15 blur-[130px] pointer-events-none"></div>

    <div class="w-full max-w-md px-4 relative z-10 animate-fade-in">

        {{-- Brand --}}
        <div class="flex flex-col items-center mb-8">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-xl shadow-brand-500/25 mb-4">
                <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                </svg>
            </div>
            <h1 class="text-2xl font-bold text-white">Buat Password Baru</h1>
            <p class="text-sm text-gray-500 mt-1">Pastikan password baru Anda minimal 8 karakter.</p>
        </div>

        <div class="glass border border-gray-800/60 rounded-3xl p-8 shadow-2xl">

            {{-- Error --}}
            @if($errors->any())
            <div class="mb-5 flex items-center gap-3 px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/30 text-red-400">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
                </svg>
                <span class="text-sm">{{ $errors->first() }}</span>
            </div>
            @endif

            <form id="reset-form" method="POST" action="{{ route('password.update') }}" class="space-y-5">
                @csrf

                {{-- Token --}}
                <input type="hidden" name="token" value="{{ $token }}">

                {{-- Email (readonly) --}}
                <div>
                    <label for="email" class="block text-sm font-medium text-gray-400 mb-2">Alamat Email</label>
                    <input type="email" id="email" name="email"
                           value="{{ old('email', $email) }}"
                           required readonly autocomplete="email"
                           class="w-full px-4 py-3 rounded-xl bg-surface-900/50 border border-gray-700/30 text-gray-400 cursor-not-allowed text-sm">
                </div>

                {{-- Password baru --}}
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-400 mb-2">Password Baru</label>
                    <div class="relative">
                        <input type="password" id="password" name="password"
                               required autocomplete="new-password"
                               class="w-full px-4 py-3 pr-11 rounded-xl bg-surface-900 border border-gray-700/50 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all"
                               placeholder="Minimal 8 karakter">
                        <button type="button" onclick="toggleVisibility('password', this)"
                                class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors" tabindex="-1">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                            </svg>
                        </button>
                    </div>
                </div>

                {{-- Konfirmasi password --}}
                <div>
                    <label for="password_confirmation" class="block text-sm font-medium text-gray-400 mb-2">Konfirmasi Password</label>
                    <div class="relative">
                        <input type="password" id="password_confirmation" name="password_confirmation"
                               required autocomplete="new-password"
                               class="w-full px-4 py-3 pr-11 rounded-xl bg-surface-900 border border-gray-700/50 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-all"
                               placeholder="Ulangi password baru">
                        <button type="button" onclick="toggleVisibility('password_confirmation', this)"
                                class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors" tabindex="-1">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                            </svg>
                        </button>
                    </div>
                </div>

                <button type="submit" id="reset-btn"
                        class="w-full py-3.5 mt-1 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 text-white text-sm font-semibold shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40 hover:from-brand-500 hover:to-brand-400 transition-all duration-200 transform hover:scale-[1.02] flex items-center justify-center gap-2">
                    <svg id="reset-spinner" class="w-4 h-4 animate-spin hidden" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span id="reset-btn-text">Reset Password</span>
                </button>
            </form>
        </div>

        <p class="text-center text-xs text-gray-600 mt-6">
            &copy; {{ date('Y') }} Diskominfotik. All rights reserved.
        </p>
    </div>

    <script>
        function toggleVisibility(inputId) {
            const input = document.getElementById(inputId);
            input.type = input.type === 'password' ? 'text' : 'password';
        }
        document.getElementById('reset-form').addEventListener('submit', function () {
            document.getElementById('reset-spinner').classList.remove('hidden');
            document.getElementById('reset-btn-text').textContent = 'Menyimpan...';
            document.getElementById('reset-btn').disabled = true;
        });
    </script>
</body>
</html>
