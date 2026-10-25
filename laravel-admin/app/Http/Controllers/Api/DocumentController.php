<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Services\AiMicroserviceClient;
use App\Services\Documents\DocumentPresenter;
use App\Services\Documents\DocumentWorkflowService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;

class DocumentController extends Controller
{
    public function __construct(
        private AiMicroserviceClient $client,
        private DocumentPresenter $presenter,
        private DocumentWorkflowService $workflow,
    ) {
    }

    /**
     * Return a paginated list of all documents with summary stats.
     */
    public function index(Request $request): JsonResponse
    {
        $documents = Document::with(['uploader', 'category', 'ekstraksiJob', 'ekstraksiHalaman'])
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        $vectorCounts = $this->client->getVectorCounts();

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
                'documents'      => $documents->map(fn ($doc) => $this->presenter->format($doc, false, $vectorCounts)),
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
        $vectorCounts = $this->client->getVectorCounts();

        return response()->json([
            'success' => true,
            'data'    => [
                'document' => $this->presenter->format($document, true, $vectorCounts),
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

        $result = $this->workflow->upload(
            $request->file('pdf_file'),
            $request->input('title'),
            $request->input('category_id'),
            Auth::user(),
        );
        $document = $result->document;

        if (!$result->aiAvailable) {
            return response()->json([
                'success' => false,
                'message' => DocumentWorkflowService::AI_UNAVAILABLE_MESSAGE,
                'data' => ['document' => $this->presenter->format($document->fresh())],
            ], 503);
        }

        return response()->json([
            'success' => true,
            'message' => "Dokumen \"{$document->title}\" berhasil diunggah dan sedang diproses.",
            'data' => ['document' => $this->presenter->format($document)],
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

        $this->workflow->replace($document, $request->file('pdf_file'), Auth::user());

        return response()->json([
            'success' => true,
            'message' => 'File dokumen berhasil diganti dan sedang diproses ulang dari awal.',
            'data' => ['document' => $this->presenter->format($document->fresh())],
        ]);
    }

    /**
     * Cancel an active or pending document AI processing.
     */
    public function cancel(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        $this->workflow->cancel($document, Auth::user());

        return response()->json([
            'success' => true,
            'message' => 'Pemrosesan dokumen berhasil dibatalkan dan resource sistem telah dibebaskan.',
            'data' => ['document' => $this->presenter->format($document->fresh())],
        ]);
    }

    /**
     * Resume / Continue (Cicil) document AI processing using the staged extraction API.
     */
    public function resume(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        if (!$this->workflow->resume($document, Auth::user())) {
            return response()->json([
                'success' => false,
                'message' => DocumentWorkflowService::AI_UNAVAILABLE_MESSAGE,
                'data' => ['document' => $this->presenter->format($document->fresh())],
            ], 503);
        }

        return response()->json([
            'success' => true,
            'message' => 'Ekstraksi dokumen berhasil dilanjutkan.',
            'data' => ['document' => $this->presenter->format($document->fresh())],
        ]);
    }

    /**
     * Delete a document, its physical file, and its ChromaDB vector embeddings.
     */
    public function destroy(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        $this->workflow->delete($document);

        return response()->json([
            'success' => true,
            'message' => 'Dokumen berhasil dihapus.',
        ]);
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
     * Preserve the existing status resolver entrypoint for callers.
     */
    public function resolveEffectiveStatus(Document $document, int $donePages = 0, int $totalPages = 0): array
    {
        return $this->presenter->resolveEffectiveStatus($document, $donePages, $totalPages);
    }

    /**
     * Get document chunks from ChromaDB via AI microservice.
     */
    public function chunks($id)
    {
        $document = Document::findOrFail($id);
        
        $chunks = $this->client->getDocumentChunks($document->id);
        
        return response()->json($chunks);
    }
}
