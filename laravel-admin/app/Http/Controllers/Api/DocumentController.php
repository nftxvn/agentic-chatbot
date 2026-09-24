<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Models\DocumentLog;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class DocumentController extends Controller
{
    /**
     * Return a paginated list of all documents with summary stats.
     */
    public function index(Request $request): JsonResponse
    {
        $documents = Document::with(['uploader', 'category', 'ekstraksiJob', 'ekstraksiHalaman'])
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        $allDocs = Document::with('ekstraksiJob')->get();

        $total           = $allDocs->count();
        $completed       = 0;
        $menungguKoreksi = 0;
        $processing      = 0;
        $failed          = 0;

        foreach ($allDocs as $doc) {
            $resolved = $this->resolveEffectiveStatus($doc);
            match ($resolved['status']) {
                'completed'        => $completed++,
                'menunggu_koreksi' => $menungguKoreksi++,
                'processing'       => $processing++,
                'failed'           => $failed++,
                default            => null,
            };
        }

        $stats = [
            'total'            => $total,
            'completed'        => $completed,
            'menunggu_koreksi' => $menungguKoreksi,
            'processing'       => $processing,
            'failed'           => $failed,
        ];

        return response()->json([
            'success' => true,
            'data'    => [
                'documents'      => $documents->map(fn ($doc) => $this->formatDocument($doc)),
                'meta'           => [
                    'current_page' => $documents->currentPage(),
                    'last_page'    => $documents->lastPage(),
                    'per_page'     => $documents->perPage(),
                    'total'        => $documents->total(),
                ],
                'stats'          => $stats,
                'has_processing' => $stats['processing'] > 0,
            ],
        ]);
    }

    /**
     * Return a single document's details and logs.
     */
    public function show(int $id): JsonResponse
    {
        $document = Document::with(['uploader', 'category', 'logs', 'ekstraksiJob'])->findOrFail($id);

        return response()->json([
            'success' => true,
            'data'    => [
                'document' => $this->formatDocument($document, true),
            ],
        ]);
    }

    /**
     * Handle a new document upload (supports PDF, DOCX, XLSX, CSV, TXT, MD, PNG, JPG, JPEG, WEBP).
     */
    public function upload(Request $request): JsonResponse
    {
        $request->validate([
            'title'       => ['required', 'string', 'max:255'],
            'pdf_file'    => ['required', 'file', 'mimes:pdf,docx,xlsx,csv,txt,md,png,jpg,jpeg,webp', 'max:51200'],
            'category_id' => ['nullable', 'integer', 'exists:document_categories,id'],
        ], [
            'title.required'    => 'Judul dokumen wajib diisi.',
            'title.max'         => 'Judul dokumen maksimal 255 karakter.',
            'pdf_file.required' => 'File dokumen wajib diunggah.',
            'pdf_file.mimes'    => 'Format file tidak diizinkan. Gunakan format: PDF, DOCX, XLSX, CSV, TXT, MD, PNG, JPG, JPEG, atau WEBP.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        $file             = $request->file('pdf_file');
        $rawFilename      = $file->getClientOriginalName();
        // Sanitize original filename (strip path traversal and unsafe characters)
        $originalFilename = preg_replace('/[^\w\s\-\.\(\)\[\]]/u', '_', basename($rawFilename));
        $sanitizedTitle   = strip_tags(trim($request->input('title')));

        // Generate a secure random hashed filename (SHA-256)
        $extension        = strtolower($file->getClientOriginalExtension() ?: $file->extension() ?: 'bin');
        $hashedName       = hash('sha256', Str::uuid()->toString() . microtime(true) . $file->getContent()) . '.' . $extension;
        $storagePath      = $file->storeAs('documents', $hashedName, 'local');
        $absolutePath     = Storage::disk('local')->path($storagePath);

        $document = Document::create([
            'title'         => $sanitizedTitle,
            'original_name' => $originalFilename,
            'file_path'     => $absolutePath,
            'status'        => 'pending',
            'pdf_type'      => 'unknown',
            'category_id'   => $request->input('category_id'),
            'uploaded_by'   => Auth::id(),
        ]);

        $document->recordLog('uploaded', "File \"{$originalFilename}\" diunggah oleh " . Auth::user()->name);

        $client = new AiMicroserviceClient();
        if (!$client->healthCheck()) {
            $document->update([
                'status'        => 'failed',
                'error_message' => 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.',
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.',
                'data'    => ['document' => $this->formatDocument($document->fresh())],
            ], 503);
        }

        $this->dispatchToAiService($document, 'new');

        return response()->json([
            'success' => true,
            'message' => "Dokumen \"{$document->title}\" berhasil diunggah dan sedang diproses.",
            'data'    => ['document' => $this->formatDocument($document)],
        ], 201);
    }

    /**
     * Replace an existing document's file.
     */
    public function replace(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'pdf_file' => ['required', 'file', 'mimes:pdf,docx,xlsx,csv,txt,md,png,jpg,jpeg,webp', 'max:51200'],
        ], [
            'pdf_file.required' => 'File dokumen wajib diunggah.',
            'pdf_file.mimes'    => 'Format file tidak diizinkan. Gunakan format: PDF, DOCX, XLSX, CSV, TXT, MD, PNG, JPG, JPEG, atau WEBP.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        $client = new AiMicroserviceClient();

        // 1. Batalkan tugas ekstraksi aktif di background jika ada
        $client->cancelDocument($document->id);

        // 2. Hapus berkas fisik lama dari disk storage
        $oldPath = $document->file_path ?? Storage::disk('local')->path($document->storage_path ?? '');
        if ($oldPath && file_exists($oldPath)) {
            @unlink($oldPath);
        }

        // 3. Bersihkan data ekstraksi lama di database (halaman & job)
        DB::table('ekstraksi_halaman')->where('document_id', $document->id)->delete();
        DB::table('ekstraksi_job')->where('document_id', $document->id)->delete();

        // 4. Bersihkan embedding vektor lama dari ChromaDB
        $client->deleteDocument($document->id);

        // 5. Simpan file baru ke storage
        $file             = $request->file('pdf_file');
        $rawFilename      = $file->getClientOriginalName();
        $originalFilename = preg_replace('/[^\w\s\-\.\(\)\[\]]/u', '_', basename($rawFilename));

        // Generate a secure random hashed filename (SHA-256)
        $extension        = strtolower($file->getClientOriginalExtension() ?: $file->extension() ?: 'bin');
        $hashedName       = hash('sha256', Str::uuid()->toString() . microtime(true) . $file->getContent()) . '.' . $extension;
        $storagePath      = $file->storeAs('documents', $hashedName, 'local');
        $absolutePath     = Storage::disk('local')->path($storagePath);

        // 6. Reset status dan metadata dokumen di database
        $document->update([
            'original_name'   => $originalFilename,
            'file_path'       => $absolutePath,
            'status'          => 'pending',
            'pdf_type'        => 'unknown',
            'error_message'   => null,
            'total_pages'     => null,
            'processed_pages' => 0,
            'total_chunks'    => null,
            'processed_at'    => null,
        ]);

        $document->recordLog('replaced', "File diganti dengan \"{$originalFilename}\" oleh " . (Auth::user()?->name ?? 'Admin'));

        // 7. Mulai proses ekstraksi ulang dari awal
        $this->dispatchToAiService($document, 'overwrite');

        return response()->json([
            'success' => true,
            'message' => 'File dokumen berhasil diganti dan sedang diproses ulang dari awal.',
            'data'    => ['document' => $this->formatDocument($document->fresh())],
        ]);
    }

    /**
     * Cancel an active or pending document AI processing.
     */
    public function cancel(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);

        $document->update([
            'status'        => 'failed',
            'error_message' => 'Pemrosesan dibatalkan oleh Admin.',
        ]);

        $document->recordLog('cancelled', 'Pemrosesan AI dibatalkan oleh ' . (Auth::user()?->name ?? 'Admin') . '.', 15);

        // Explicitly cancel background task in Python AI & release GPU/CPU memory
        $client = new AiMicroserviceClient();
        $client->cancelDocument($document->id);

        return response()->json([
            'success' => true,
            'message' => 'Pemrosesan dokumen berhasil dibatalkan dan resource sistem telah dibebaskan.',
            'data'    => ['document' => $this->formatDocument($document->fresh())],
        ]);
    }

    /**
     * Resume / Continue (Cicil) document AI processing using the staged extraction API.
     */
    public function resume(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        $client   = new AiMicroserviceClient();

        if (!$client->healthCheck()) {
            $document->update([
                'status'        => 'failed',
                'error_message' => 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.',
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.',
                'data'    => ['document' => $this->formatDocument($document->fresh())],
            ], 503);
        }

        $document->update([
            'status'        => 'processing',
            'error_message' => null,
        ]);

        $document->recordLog('resumed', 'Ekstraksi AI dilanjutkan kembali oleh ' . (Auth::user()?->name ?? 'Admin') . '.', 15);

        $categoryOptions = $this->buildCategoryOptions($document);

        // Start / resume staged extraction in Python AI
        $client->mulaiEkstraksi($document->id, null, $categoryOptions);

        return response()->json([
            'success' => true,
            'message' => 'Ekstraksi dokumen berhasil dilanjutkan.',
            'data'    => ['document' => $this->formatDocument($document->fresh())],
        ]);
    }

    /**
     * Delete a document, its physical file, and its ChromaDB vector embeddings.
     */
    public function destroy(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);

        $filePath = $document->file_path ?? Storage::disk('local')->path($document->storage_path ?? '');
        if ($filePath && file_exists($filePath)) {
            @unlink($filePath);
        }

        $document->recordLog('deleted', 'Dokumen dan seluruh vektor terkait dihapus permanen oleh ' . (Auth::user()?->name ?? 'Admin') . '.');

        // Delete vectors from ChromaDB via Python AI microservice
        $client = new AiMicroserviceClient();
        $client->deleteDocument($document->id);

        // Bersihkan data ekstraksi bertahap dari database
        DB::table('ekstraksi_halaman')->where('document_id', $document->id)->delete();
        DB::table('ekstraksi_job')->where('document_id', $document->id)->delete();

        $document->delete();

        return response()->json([
            'success' => true,
            'message' => 'Dokumen berhasil dihapus.',
        ]);
    }

    /**
     * Build category extraction options for Python AI.
     */
    protected function buildCategoryOptions(Document $document): array
    {
        $category = $document->category;
        if (!$category && $document->category_id) {
            $category = \App\Models\DocumentCategory::find($document->category_id);
        }

        $kataKunci = data_get($category, 'prompt_variables.kata_kunci')
            ?? data_get($category, 'prompt_variables.job_titles', []);
        $customPrompts = data_get($category, 'prompt_variables.custom_prompts', []);

        return [
            'category_prompt' => $category?->vision_prompt,
            'job_titles'      => is_array($kataKunci) ? implode(', ', $kataKunci) : $kataKunci,
            'vision_model'    => $category?->vision_model,
            'custom_prompts'  => !empty($customPrompts) ? $customPrompts : null,
        ];
    }

    /**
     * Serve a document file.
     */
    public function servePdf(int $id): mixed
    {
        $document = Document::findOrFail($id);
        $filePath = $document->file_path;

        if (!$filePath || !file_exists($filePath)) {
            $filePath = Storage::disk('local')->path($document->storage_path ?? '');
        }

        if (!file_exists($filePath)) {
            return response()->json(['success' => false, 'message' => 'File tidak ditemukan.'], 404);
        }

        $mimeType = @mime_content_type($filePath) ?: 'application/octet-stream';
        $filename = $document->original_name ?? $document->original_filename ?? 'document';

        return response()->file($filePath, [
            'Content-Type'        => $mimeType,
            'Content-Disposition' => 'inline; filename="' . addslashes($filename) . '"',
        ]);
    }

    /**
     * Dispatch document processing to the AI microservice using staged extraction.
     */
    protected function dispatchToAiService(Document $document, string $action): void
    {
        $client = new AiMicroserviceClient();

        $document->update([
            'status'        => 'processing',
            'error_message' => null,
        ]);

        $document->recordLog('processing', 'Dokumen dikirim ke antrean Ekstraksi AI bertahap.', 15);

        $categoryOptions = $this->buildCategoryOptions($document);

        // Dispatch staged extraction: every page is saved to database immediately upon completion
        $result = $client->mulaiEkstraksi($document->id, null, $categoryOptions);

        if (!$result['success']) {
            $document->recordLog('failed', $result['message'] ?? 'Gagal memulai ekstraksi', 10);

            $document->update([
                'status'        => 'pending',
                'error_message' => $result['message'] ?? 'Gagal memulai ekstraksi',
            ]);
        }
    }

    /**
     * Determine the unified effective status and label for a document.
     */
    public function resolveEffectiveStatus(Document $document, int $donePages = 0, int $totalPages = 0): array
    {
        $job    = $document->ekstraksiJob;
        $status = $document->status;

        // 1. Selesai (Completed / Indexed to corpus)
        if ($job?->status === 'selesai' || $status === 'completed') {
            return ['status' => 'completed', 'label' => 'Selesai'];
        }

        // 2. Menunggu Verifikasi (All pages extracted, waiting for human admin review)
        if ($job?->status === 'menunggu_koreksi' || $status === 'menunggu_koreksi') {
            return ['status' => 'menunggu_koreksi', 'label' => 'Menunggu Verifikasi'];
        }

        // 3. Dijeda (Paused)
        if ($job?->status === 'jeda' || $status === 'paused') {
            return ['status' => 'jeda', 'label' => 'Dijeda'];
        }

        // 3b. Menunggu Jeda (Sedang menyelesaikan halaman aktif sebelum jeda)
        if ($job?->jeda_diminta) {
            return ['status' => 'processing', 'label' => 'Menjeda...'];
        }

        // 4. Gagal (Failed)
        if ($job?->status === 'gagal' || $status === 'failed') {
            return ['status' => 'failed', 'label' => 'Gagal'];
        }

        // 5. Sedang Berjalan / Antre (Processing)
        if ($job?->status === 'berjalan' || $job?->status === 'ekstraksi' || $job?->status === 'antre' || $status === 'processing') {
            return ['status' => 'processing', 'label' => 'Memproses'];
        }

        return [
            'status' => $status ?? 'pending',
            'label'  => $document->status_badge['label'] ?? 'Menunggu',
        ];
    }

    /**
     * Format a document model for API response.
     */
    protected function formatDocument(Document $document, bool $withLogs = false): array
    {
        $job = $document->ekstraksiJob;

        $savedCount  = $document->relationLoaded('ekstraksiHalaman') ? $document->ekstraksiHalaman->count() : $document->ekstraksiHalaman()->count();
        $donePages   = max($savedCount, (int) ($document->processed_pages ?? 0), (int) ($job?->halaman_selesai ?? 0));
        $totalPages  = $document->total_pages ?? $job?->halaman_total ?? 0;
        $percent     = ($totalPages > 0) ? min(100, (int) round(($donePages / $totalPages) * 100)) : ($job?->persen ?? 0);

        $resolved    = $this->resolveEffectiveStatus($document, $donePages, $totalPages);
        $status      = $resolved['status'];
        $statusLabel = $resolved['label'];

        $data = [
            'id'                => $document->id,
            'title'             => $document->title,
            'original_filename' => $document->original_name ?? $document->original_filename,
            'original_name'     => $document->original_name ?? $document->original_filename,
            'file_path'         => $document->file_path,
            'status'            => $status,
            'status_label'      => $statusLabel,
            'pdf_type'          => $document->pdf_type,
            'pdf_type_label'    => $document->pdf_type_label,
            'category_id'       => $document->category_id,
            'category_name'     => $document->category?->name ?? 'Umum',
            'category_ui_layout'=> $document->category?->ui_layout ?? 'general',
            'total_pages'       => $totalPages,
            'processed_pages'   => $donePages,
            'total_chunks'      => $document->total_chunks,
            'error_message'     => $document->error_message,
            'uploaded_by'       => $document->uploader?->name,
            'pdf_url'           => url("/api/documents/{$document->id}/pdf"),
            'created_at'        => $document->created_at ? \Carbon\Carbon::parse($document->created_at)->toIso8601String() : null,
            'processed_at'      => $document->processed_at ? \Carbon\Carbon::parse($document->processed_at)->toIso8601String() : null,

            // Staged extraction progress
            'ekstraksi_status'  => $job?->status,
            'jeda_diminta'      => (bool) $job?->jeda_diminta,
            'halaman_selesai'   => $donePages,
            'persen_ekstraksi'  => $percent,
        ];

        if ($withLogs) {
            $data['logs'] = $document->logs->map(fn ($log) => [
                'id'          => $log->id,
                'action'      => $log->action,
                'action_label'=> $log->action_label,
                'action_color'=> $log->action_color,
                'details'     => $log->details,
                'created_at'  => $log->created_at ? \Carbon\Carbon::parse($log->created_at)->toIso8601String() : null,
            ])->values();
        }

        return $data;
    }

    /**
     * Get document chunks from ChromaDB via AI microservice.
     */
    public function chunks($id)
    {
        $document = Document::findOrFail($id);
        
        $aiClient = new \App\Services\AiMicroserviceClient();
        $chunks = $aiClient->getDocumentChunks($document->id);
        
        return response()->json($chunks);
    }
}
