@extends('layouts.admin')

@section('title', 'Manajemen Dokumen')
@section('page-title', 'Manajemen Dokumen')
@section('page-description', 'Kelola dokumen PDF dan pemrosesan AI')

@section('page-actions')
<button onclick="document.getElementById('upload-modal').classList.remove('hidden')"
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 text-white text-sm font-semibold shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40 hover:from-brand-500 hover:to-brand-400 transition-all duration-200 transform hover:scale-[1.02]">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
    </svg>
    Unggah Dokumen
</button>
@endsection

@section('content')
{{-- Stats Cards --}}
<div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
    @php
        $total = $documents->total();
        $completed = App\Models\Document::where('status', 'completed')->count();
        $processing = App\Models\Document::where('status', 'processing')->count();
        $failed = App\Models\Document::where('status', 'failed')->count();
    @endphp

    <div class="bg-surface-800 border border-gray-800/50 rounded-2xl p-5 hover:border-gray-700/50 transition-colors">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wider">Total Dokumen</p>
                <p class="text-2xl font-bold text-white mt-1">{{ $total }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-brand-600/10 flex items-center justify-center">
                <svg class="w-6 h-6 text-brand-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
            </div>
        </div>
    </div>

    <div class="bg-surface-800 border border-gray-800/50 rounded-2xl p-5 hover:border-gray-700/50 transition-colors">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wider">Selesai</p>
                <p class="text-2xl font-bold text-green-400 mt-1">{{ $completed }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-green-900/20 flex items-center justify-center">
                <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            </div>
        </div>
    </div>

    <div class="bg-surface-800 border border-gray-800/50 rounded-2xl p-5 hover:border-gray-700/50 transition-colors">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wider">Memproses</p>
                <p class="text-2xl font-bold text-yellow-400 mt-1">{{ $processing }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-yellow-900/20 flex items-center justify-center">
                <svg class="w-6 h-6 text-yellow-400 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
            </div>
        </div>
    </div>

    <div class="bg-surface-800 border border-gray-800/50 rounded-2xl p-5 hover:border-gray-700/50 transition-colors">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wider">Gagal</p>
                <p class="text-2xl font-bold text-red-400 mt-1">{{ $failed }}</p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-red-900/20 flex items-center justify-center">
                <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            </div>
        </div>
    </div>
</div>

{{-- Documents Table --}}
<div class="bg-surface-800 border border-gray-800/50 rounded-2xl overflow-hidden">
    <div class="px-6 py-4 border-b border-gray-800/50 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-white">Daftar Dokumen</h3>
        @if($hasProcessing)
        <div class="flex items-center gap-2 text-xs text-yellow-400">
            <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-yellow-400"></span>
            </span>
            Auto-refresh aktif
        </div>
        @endif
    </div>

    <div id="documents-table-body">
        @if($documents->isEmpty())
        <div class="text-center py-16">
            <svg class="w-16 h-16 text-gray-700 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            <p class="text-gray-500 text-sm font-medium">Belum ada dokumen</p>
            <p class="text-gray-600 text-xs mt-1">Klik tombol "Unggah Dokumen" untuk memulai</p>
        </div>
        @else
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <th class="px-6 py-3">Nama Dokumen</th>
                        <th class="px-6 py-3">File Asli</th>
                        <th class="px-6 py-3">Status</th>
                        <th class="px-6 py-3">Tipe PDF</th>
                        <th class="px-6 py-3">Chunks</th>
                        <th class="px-6 py-3">Tanggal Upload</th>
                        <th class="px-6 py-3 text-right">Aksi</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-800/50">
                    @foreach($documents as $doc)
                    <tr class="hover:bg-white/[0.02] transition-colors group">
                        <td class="px-6 py-4">
                            <a href="{{ route('documents.show', $doc->id) }}" class="text-sm font-medium text-white hover:text-brand-400 transition-colors">
                                {{ $doc->title }}
                            </a>
                        </td>
                        <td class="px-6 py-4">
                            <span class="text-xs text-gray-400 font-mono bg-surface-900 px-2 py-1 rounded-lg">
                                {{ Str::limit($doc->original_filename, 30) }}
                            </span>
                        </td>
                        <td class="px-6 py-4">
                            @php $badge = $doc->status_badge; @endphp
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold {{ $badge['bg'] }} {{ $badge['text'] }} {{ $doc->status === 'processing' ? 'pulse-processing' : '' }}">
                                @if($doc->status === 'processing')
                                <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                @endif
                                {{ $badge['label'] }}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-400">
                            {{ $doc->pdf_type_label }}
                        </td>
                        <td class="px-6 py-4 text-sm text-gray-400">
                            {{ $doc->total_chunks ?? '—' }}
                        </td>
                        <td class="px-6 py-4 text-xs text-gray-500">
                            {{ $doc->created_at->format('d M Y H:i') }}
                        </td>
                        <td class="px-6 py-4 text-right">
                            <div class="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <a href="{{ route('documents.show', $doc->id) }}"
                                   class="p-2 rounded-lg text-gray-400 hover:text-brand-400 hover:bg-brand-600/10 transition-colors"
                                   title="Lihat Detail">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                                    </svg>
                                </a>
                                <form action="{{ route('documents.destroy', $doc->id) }}" method="POST"
                                      onsubmit="return confirm('Yakin ingin menghapus dokumen ini?')">
                                    @csrf
                                    @method('DELETE')
                                    <button type="submit"
                                            class="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                                            title="Hapus Dokumen">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                        </svg>
                                    </button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        {{-- Pagination --}}
        @if($documents->hasPages())
        <div class="px-6 py-4 border-t border-gray-800/50">
            {{ $documents->links() }}
        </div>
        @endif
        @endif
    </div>
</div>

{{-- Upload Modal --}}
<div id="upload-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center">
    {{-- Backdrop --}}
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="document.getElementById('upload-modal').classList.add('hidden')"></div>

    {{-- Modal Content --}}
    <div class="relative w-full max-w-lg mx-4 bg-surface-800 border border-gray-700/50 rounded-2xl shadow-2xl animate-fade-in">
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-800/50">
            <h3 class="text-lg font-semibold text-white">Unggah Dokumen Baru</h3>
            <button onclick="document.getElementById('upload-modal').classList.add('hidden')"
                    class="text-gray-400 hover:text-white transition-colors">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                </svg>
            </button>
        </div>

        <form action="{{ route('documents.upload') }}" method="POST" enctype="multipart/form-data" class="p-6 space-y-5">
            @csrf
            <div>
                <label for="upload-title" class="block text-sm font-medium text-gray-300 mb-2">Judul Dokumen</label>
                <input type="text" name="title" id="upload-title" required
                       class="w-full px-4 py-2.5 rounded-xl bg-surface-900 border border-gray-700/50 text-white text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-colors"
                       placeholder="Contoh: SOP Penanganan Server Down">
            </div>

            <div>
                <label for="upload-file" class="block text-sm font-medium text-gray-300 mb-2">File PDF</label>
                <div class="relative">
                    <input type="file" name="pdf_file" id="upload-file" accept=".pdf" required
                           class="w-full px-4 py-2.5 rounded-xl bg-surface-900 border border-gray-700/50 text-white text-sm file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-600 file:text-white hover:file:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-colors cursor-pointer">
                </div>
                <p class="text-xs text-gray-500 mt-2">Format: PDF • Maks: 50MB</p>
            </div>

            <div class="flex justify-end gap-3 pt-2">
                <button type="button" onclick="document.getElementById('upload-modal').classList.add('hidden')"
                        class="px-4 py-2.5 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors">
                    Batal
                </button>
                <button type="submit"
                        class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-brand-500 text-white text-sm font-semibold shadow-lg shadow-brand-500/25 hover:shadow-brand-500/40 transition-all duration-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                    </svg>
                    Unggah
                </button>
            </div>
        </form>
    </div>
</div>
@endsection

@push('scripts')
<script>
    // Auto-refresh if any document is processing
    @if($hasProcessing)
    (function autoRefresh() {
        const INTERVAL = 10000; // 10 seconds

        setInterval(async () => {
            try {
                const response = await fetch(window.location.href);
                if (!response.ok) return;

                const html = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const newTableBody = doc.getElementById('documents-table-body');
                const currentTableBody = document.getElementById('documents-table-body');

                if (newTableBody && currentTableBody) {
                    currentTableBody.innerHTML = newTableBody.innerHTML;
                }

                // Update stats cards
                const newContent = doc.querySelector('.grid.grid-cols-1');
                const currentContent = document.querySelector('.grid.grid-cols-1');
                if (newContent && currentContent) {
                    currentContent.innerHTML = newContent.innerHTML;
                }

                // Check if we should stop auto-refreshing
                if (!html.includes('pulse-processing')) {
                    // No more processing documents, reload to remove auto-refresh indicator
                    window.location.reload();
                }
            } catch (e) {
                console.warn('Auto-refresh failed:', e);
            }
        }, INTERVAL);
    })();
    @endif
</script>
@endpush
