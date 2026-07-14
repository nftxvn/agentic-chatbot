@extends('layouts.admin')

@section('title', $document->title)
@section('page-title', $document->title)
@section('page-description', 'Detail dokumen dan pratinjau PDF')

@section('page-actions')
<a href="{{ route('dashboard') }}"
   class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-colors">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
    </svg>
    Kembali
</a>
@endsection

@section('content')
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    {{-- Left Column: Metadata + Actions --}}
    <div class="lg:col-span-1 space-y-6">
        {{-- Document Info Card --}}
        <div class="bg-surface-800 border border-gray-800/50 rounded-2xl overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-800/50">
                <h3 class="text-sm font-semibold text-white">Informasi Dokumen</h3>
            </div>
            <div class="p-6 space-y-4">
                {{-- Status --}}
                <div>
                    <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Status Pemrosesan</p>
                    @php $badge = $document->status_badge; @endphp
                    <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold {{ $badge['bg'] }} {{ $badge['text'] }} {{ $document->status === 'processing' ? 'pulse-processing' : '' }}">
                        @if($document->status === 'processing')
                        <svg class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        @elseif($document->status === 'completed')
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                        @elseif($document->status === 'failed')
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                        @endif
                        {{ $badge['label'] }}
                    </span>
                </div>

                @if($document->error_message)
                <div class="px-3 py-2 rounded-xl bg-red-900/20 border border-red-800/30">
                    <p class="text-xs font-medium text-red-400">{{ $document->error_message }}</p>
                </div>
                @endif

                {{-- Metadata Grid --}}
                <div class="space-y-3">
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">File Asli</span>
                        <span class="text-xs text-gray-300 font-mono bg-surface-900 px-2 py-0.5 rounded-lg max-w-[180px] truncate" title="{{ $document->original_filename }}">
                            {{ $document->original_filename }}
                        </span>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">Tipe PDF</span>
                        <span class="text-xs text-gray-300">{{ $document->pdf_type_label }}</span>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">Jumlah Halaman</span>
                        <span class="text-xs text-gray-300">{{ $document->total_pages ?? '—' }}</span>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">Jumlah Chunks</span>
                        <span class="text-xs text-gray-300">{{ $document->total_chunks ?? '—' }}</span>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">Diunggah Oleh</span>
                        <span class="text-xs text-gray-300">{{ $document->uploader->name ?? '—' }}</span>
                    </div>
                    <div class="flex justify-between items-center py-2 border-b border-gray-800/30">
                        <span class="text-xs text-gray-500">Tanggal Upload</span>
                        <span class="text-xs text-gray-300">{{ $document->created_at->format('d M Y H:i') }}</span>
                    </div>
                    <div class="flex justify-between items-center py-2">
                        <span class="text-xs text-gray-500">Selesai Diproses</span>
                        <span class="text-xs text-gray-300">{{ $document->processed_at ? $document->processed_at->format('d M Y H:i') : '—' }}</span>
                    </div>
                </div>
            </div>
        </div>

        {{-- Replace PDF Card --}}
        <div class="bg-surface-800 border border-gray-800/50 rounded-2xl overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-800/50">
                <h3 class="text-sm font-semibold text-white">Ganti File PDF</h3>
            </div>
            <form action="{{ route('documents.replace', $document->id) }}" method="POST" enctype="multipart/form-data" class="p-6 space-y-4">
                @csrf
                <div>
                    <input type="file" name="pdf_file" accept=".pdf" required
                           class="w-full px-4 py-2.5 rounded-xl bg-surface-900 border border-gray-700/50 text-white text-sm file:mr-4 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-600 file:text-white hover:file:bg-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 transition-colors cursor-pointer">
                    <p class="text-xs text-gray-500 mt-2">File baru akan menggantikan file lama. Proses embedding akan dijalankan ulang.</p>
                </div>
                <button type="submit"
                        class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-amber-600/20 border border-amber-700/30 text-amber-400 text-sm font-semibold hover:bg-amber-600/30 transition-colors"
                        onclick="return confirm('Yakin ingin mengganti file PDF ini? Proses embedding akan dijalankan ulang.')">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
                    </svg>
                    Ganti & Proses Ulang
                </button>
            </form>
        </div>

        {{-- Delete Card --}}
        <div class="bg-surface-800 border border-red-900/30 rounded-2xl overflow-hidden">
            <div class="p-6">
                <h3 class="text-sm font-semibold text-red-400 mb-2">Zona Berbahaya</h3>
                <p class="text-xs text-gray-500 mb-4">Menghapus dokumen akan menghapus file PDF dan seluruh data terkait secara permanen.</p>
                <form action="{{ route('documents.destroy', $document->id) }}" method="POST">
                    @csrf
                    @method('DELETE')
                    <button type="submit"
                            class="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-red-600/20 border border-red-700/30 text-red-400 text-sm font-semibold hover:bg-red-600/30 transition-colors"
                            onclick="return confirm('PERINGATAN: Dokumen ini akan dihapus permanen. Lanjutkan?')">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                        Hapus Dokumen
                    </button>
                </form>
            </div>
        </div>
    </div>

    {{-- Right Column: PDF Preview + Logs --}}
    <div class="lg:col-span-2 space-y-6">
        {{-- PDF Preview --}}
        <div class="bg-surface-800 border border-gray-800/50 rounded-2xl overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-800/50 flex items-center justify-between">
                <h3 class="text-sm font-semibold text-white">Pratinjau PDF</h3>
                <a href="{{ route('documents.pdf', $document->id) }}" target="_blank"
                   class="inline-flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 transition-colors">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                    </svg>
                    Buka di Tab Baru
                </a>
            </div>
            <div class="aspect-[4/3] bg-surface-900">
                <iframe src="{{ route('documents.pdf', $document->id) }}"
                        class="w-full h-full border-0"
                        title="Pratinjau {{ $document->title }}">
                    <p class="text-gray-500 text-sm p-4">Browser Anda tidak mendukung pratinjau PDF.</p>
                </iframe>
            </div>
        </div>

        {{-- Processing Logs Timeline --}}
        <div class="bg-surface-800 border border-gray-800/50 rounded-2xl overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-800/50">
                <h3 class="text-sm font-semibold text-white">Riwayat Pemrosesan</h3>
            </div>
            <div class="p-6">
                @if($document->logs->isEmpty())
                <p class="text-sm text-gray-500 text-center py-4">Belum ada riwayat pemrosesan.</p>
                @else
                <div class="relative">
                    {{-- Timeline line --}}
                    <div class="absolute left-[15px] top-2 bottom-2 w-px bg-gray-800"></div>

                    <div class="space-y-4">
                        @foreach($document->logs as $log)
                        <div class="relative flex gap-4">
                            {{-- Timeline dot --}}
                            <div class="relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                                @switch($log->action_color)
                                    @case('blue') bg-blue-900/30 border border-blue-700/50 @break
                                    @case('yellow') bg-yellow-900/30 border border-yellow-700/50 @break
                                    @case('purple') bg-purple-900/30 border border-purple-700/50 @break
                                    @case('indigo') bg-indigo-900/30 border border-indigo-700/50 @break
                                    @case('green') bg-green-900/30 border border-green-700/50 @break
                                    @case('red') bg-red-900/30 border border-red-700/50 @break
                                    @case('orange') bg-orange-900/30 border border-orange-700/50 @break
                                    @default bg-gray-800 border border-gray-700/50 @break
                                @endswitch">
                                @switch($log->action)
                                    @case('uploaded')
                                        <svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>
                                        @break
                                    @case('processing')
                                        <svg class="w-3.5 h-3.5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                                        @break
                                    @case('completed')
                                        <svg class="w-3.5 h-3.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                                        @break
                                    @case('failed')
                                        <svg class="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                                        @break
                                    @case('replaced')
                                        <svg class="w-3.5 h-3.5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                                        @break
                                    @default
                                        <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                                @endswitch
                            </div>

                            {{-- Log content --}}
                            <div class="flex-1 pb-1">
                                <div class="flex items-center gap-2 mb-0.5">
                                    <span class="text-sm font-medium text-white">{{ $log->action_label }}</span>
                                    <span class="text-xs text-gray-600">{{ $log->created_at ? \Carbon\Carbon::parse($log->created_at)->format('d M Y H:i:s') : '' }}</span>
                                </div>
                                @if($log->details)
                                <p class="text-xs text-gray-400 leading-relaxed">{{ $log->details }}</p>
                                @endif
                            </div>
                        </div>
                        @endforeach
                    </div>
                </div>
                @endif
            </div>
        </div>
    </div>
</div>

@if($document->status === 'processing')
@push('scripts')
<script>
    // Auto-refresh every 10 seconds while document is processing
    setInterval(() => { window.location.reload(); }, 10000);
</script>
@endpush
@endif
@endsection
