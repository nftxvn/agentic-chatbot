<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Models\DocumentLog;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;

class DocumentController extends Controller
{
    /**
     * Return a paginated list of all documents with summary stats.
     */
    public function index(Request $request): JsonResponse
    {
        $documents = Document::with('uploader')
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        $stats = [
            'total'      => Document::count(),
            'completed'  => Document::where('status', 'completed')->count(),
            'processing' => Document::where('status', 'processing')->count(),
            'failed'     => Document::where('status', 'failed')->count(),
        ];

        return response()->json([
            'success' => true,
            'data'    => [
                'documents' => $documents->map(fn ($doc) => $this->formatDocument($doc)),
                'meta'      => [
                    'current_page' => $documents->currentPage(),
                    'last_page'    => $documents->lastPage(),
                    'per_page'     => $documents->perPage(),
                    'total'        => $documents->total(),
                ],
                'stats'         => $stats,
                'has_processing' => $stats['processing'] > 0,
            ],
        ]);
    }

    /**
     * Return a single document's details and logs.
     */
    public function show(int $id): JsonResponse
    {
        $document = Document::with(['uploader', 'logs'])->findOrFail($id);

        return response()->json([
            'success' => true,
            'data'    => [
                'document' => $this->formatDocument($document, true),
            ],
        ]);
    }

    /**
     * Handle a new PDF document upload.
     */
    public function upload(Request $request): JsonResponse
    {
        $request->validate([
            'title'    => ['required', 'string', 'max:255'],
            'pdf_file' => ['required', 'file', 'mimes:pdf', 'max:51200'],
        ], [
            'title.required'    => 'Judul dokumen wajib diisi.',
            'pdf_file.required' => 'File PDF wajib diunggah.',
            'pdf_file.mimes'    => 'File harus berformat PDF.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        $file            = $request->file('pdf_file');
        $originalFilename = $file->getClientOriginalName();
        $storagePath     = $file->store('documents', 'local');

        $document = Document::create([
            'title'             => $request->input('title'),
            'original_filename' => $originalFilename,
            'storage_path'      => $storagePath,
            'status'            => 'pending',
            'pdf_type'          => 'unknown',
            'uploaded_by'       => Auth::id(),
        ]);

        DocumentLog::create([
            'document_id' => $document->id,
            'action'      => 'uploaded',
            'details'     => "File \"{$originalFilename}\" diunggah oleh " . Auth::user()->name,
        ]);

        $this->dispatchToAiService($document, 'new');

        return response()->json([
            'success' => true,
            'message' => "Dokumen \"{$document->title}\" berhasil diunggah dan sedang diproses.",
            'data'    => ['document' => $this->formatDocument($document)],
        ], 201);
    }

    /**
     * Replace an existing document's PDF file.
     */
    public function replace(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'pdf_file' => ['required', 'file', 'mimes:pdf', 'max:51200'],
        ], [
            'pdf_file.required' => 'File PDF wajib diunggah.',
            'pdf_file.mimes'    => 'File harus berformat PDF.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        if (Storage::disk('local')->exists($document->storage_path)) {
            Storage::disk('local')->delete($document->storage_path);
        }

        $file            = $request->file('pdf_file');
        $originalFilename = $file->getClientOriginalName();
        $storagePath     = $file->store('documents', 'local');

        $document->update([
            'original_filename' => $originalFilename,
            'storage_path'      => $storagePath,
            'status'            => 'pending',
            'pdf_type'          => 'unknown',
            'error_message'     => null,
            'total_pages'       => null,
            'total_chunks'      => null,
            'processed_at'      => null,
        ]);

        DocumentLog::create([
            'document_id' => $document->id,
            'action'      => 'replaced',
            'details'     => "File diganti dengan \"{$originalFilename}\" oleh " . Auth::user()->name,
        ]);

        $this->dispatchToAiService($document, 'overwrite');

        return response()->json([
            'success' => true,
            'message' => 'File PDF berhasil diganti dan sedang diproses ulang.',
            'data'    => ['document' => $this->formatDocument($document->fresh())],
        ]);
    }

    /**
     * Delete a document and its associated file.
     */
    public function destroy(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);

        if (Storage::disk('local')->exists($document->storage_path)) {
            Storage::disk('local')->delete($document->storage_path);
        }

        $title = $document->title;
        $document->delete();

        return response()->json([
            'success' => true,
            'message' => "Dokumen \"{$title}\" berhasil dihapus.",
        ]);
    }

    /**
     * Serve a PDF file (kept as web route, uses session cookie auth).
     * This method stays for the /api/documents/{id}/pdf endpoint.
     */
    public function servePdf(int $id): mixed
    {
        $document = Document::findOrFail($id);
        $filePath = Storage::disk('local')->path($document->storage_path);

        if (!file_exists($filePath)) {
            return response()->json(['success' => false, 'message' => 'File tidak ditemukan.'], 404);
        }

        return response()->file($filePath, [
            'Content-Type'        => 'application/pdf',
            'Content-Disposition' => 'inline; filename="' . $document->original_filename . '"',
        ]);
    }

    /**
     * Dispatch document processing to the AI microservice.
     */
    protected function dispatchToAiService(Document $document, string $action): void
    {
        $client   = new AiMicroserviceClient();
        $filePath = Storage::disk('local')->path($document->storage_path);

        $document->update(['status' => 'processing']);

        DocumentLog::create([
            'document_id' => $document->id,
            'action'      => 'processing',
            'details'     => 'Dokumen dikirim ke AI Service untuk diproses.',
        ]);

        $result = $client->processDocument($document->id, $filePath, $action);

        if (!$result['success']) {
            DocumentLog::create([
                'document_id' => $document->id,
                'action'      => 'failed',
                'details'     => $result['message'],
            ]);

            if ($result['data'] === null) {
                $document->update([
                    'status'        => 'pending',
                    'error_message' => $result['message'],
                ]);
            }
        }
    }

    /**
     * Format a document model for API response.
     */
    protected function formatDocument(Document $document, bool $withLogs = false): array
    {
        $badge = $document->status_badge;

        $data = [
            'id'                => $document->id,
            'title'             => $document->title,
            'original_filename' => $document->original_filename,
            'status'            => $document->status,
            'status_label'      => $badge['label'],
            'pdf_type'          => $document->pdf_type,
            'pdf_type_label'    => $document->pdf_type_label,
            'total_pages'       => $document->total_pages,
            'total_chunks'      => $document->total_chunks,
            'error_message'     => $document->error_message,
            'uploaded_by'       => $document->uploader?->name,
            'pdf_url'           => route('api.documents.pdf', $document->id),
            'created_at'        => $document->created_at ? \Carbon\Carbon::parse($document->created_at)->toIso8601String() : null,
            'processed_at'      => $document->processed_at ? \Carbon\Carbon::parse($document->processed_at)->toIso8601String() : null,
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
