<?php

namespace App\Http\Controllers;

use App\Models\Document;
use App\Models\DocumentLog;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;

class DocumentController extends Controller
{
    /**
     * Display a paginated list of all documents.
     */
    public function index(Request $request)
    {
        $documents = Document::with('uploader')
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        // Check if any documents are still processing (for auto-refresh)
        $hasProcessing = Document::where('status', 'processing')->exists();

        return view('documents.index', compact('documents', 'hasProcessing'));
    }

    /**
     * Display a single document's details, logs, and PDF preview.
     */
    public function show(int $id)
    {
        $document = Document::with(['uploader', 'logs'])->findOrFail($id);

        return view('documents.show', compact('document'));
    }

    /**
     * Handle a new PDF document upload.
     */
    public function upload(Request $request)
    {
        $request->validate([
            'title' => 'required|string|max:255',
            'pdf_file' => 'required|file|mimes:pdf|max:51200', // Max 50MB
        ], [
            'title.required' => 'Judul dokumen wajib diisi.',
            'pdf_file.required' => 'File PDF wajib diunggah.',
            'pdf_file.mimes' => 'File harus berformat PDF.',
            'pdf_file.max' => 'Ukuran file maksimal 50MB.',
        ]);

        $file = $request->file('pdf_file');
        $originalFilename = $file->getClientOriginalName();

        // Store the file
        $storagePath = $file->store('documents', 'local');

        // Create the document record
        $document = Document::create([
            'title' => $request->input('title'),
            'original_filename' => $originalFilename,
            'storage_path' => $storagePath,
            'status' => 'pending',
            'pdf_type' => 'unknown',
            'uploaded_by' => Auth::id(),
        ]);

        // Log the upload
        DocumentLog::create([
            'document_id' => $document->id,
            'action' => 'uploaded',
            'details' => "File \"{$originalFilename}\" diunggah oleh " . Auth::user()->name,
        ]);

        // Dispatch processing to AI microservice
        $this->dispatchToAiService($document, 'new');

        return redirect()
            ->route('documents.show', $document->id)
            ->with('success', "Dokumen \"{$document->title}\" berhasil diunggah dan sedang diproses.");
    }

    /**
     * Handle replacing an existing document's PDF file.
     */
    public function replace(int $id, Request $request)
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'pdf_file' => 'required|file|mimes:pdf|max:51200',
        ], [
            'pdf_file.required' => 'File PDF wajib diunggah.',
            'pdf_file.mimes' => 'File harus berformat PDF.',
            'pdf_file.max' => 'Ukuran file maksimal 50MB.',
        ]);

        // Delete the old file
        if (Storage::disk('local')->exists($document->storage_path)) {
            Storage::disk('local')->delete($document->storage_path);
        }

        $file = $request->file('pdf_file');
        $originalFilename = $file->getClientOriginalName();

        // Store the new file
        $storagePath = $file->store('documents', 'local');

        // Update the document record
        $document->update([
            'original_filename' => $originalFilename,
            'storage_path' => $storagePath,
            'status' => 'pending',
            'pdf_type' => 'unknown',
            'error_message' => null,
            'total_pages' => null,
            'total_chunks' => null,
            'processed_at' => null,
        ]);

        // Log the replacement
        DocumentLog::create([
            'document_id' => $document->id,
            'action' => 'replaced',
            'details' => "File diganti dengan \"{$originalFilename}\" oleh " . Auth::user()->name,
        ]);

        // Dispatch processing to AI microservice with overwrite action
        $this->dispatchToAiService($document, 'overwrite');

        return redirect()
            ->route('documents.show', $document->id)
            ->with('success', 'File PDF berhasil diganti dan sedang diproses ulang.');
    }

    /**
     * Delete a document and its associated file.
     */
    public function destroy(int $id)
    {
        $document = Document::findOrFail($id);

        // Delete the file from storage
        if (Storage::disk('local')->exists($document->storage_path)) {
            Storage::disk('local')->delete($document->storage_path);
        }

        $title = $document->title;
        $document->delete(); // Cascades to document_logs

        return redirect()
            ->route('dashboard')
            ->with('success', "Dokumen \"{$title}\" berhasil dihapus.");
    }

    /**
     * Serve the PDF file for iframe preview.
     */
    public function servePdf(int $id)
    {
        $document = Document::findOrFail($id);

        $filePath = Storage::disk('local')->path($document->storage_path);

        if (!file_exists($filePath)) {
            abort(404, 'File PDF tidak ditemukan.');
        }

        return response()->file($filePath, [
            'Content-Type' => 'application/pdf',
            'Content-Disposition' => 'inline; filename="' . $document->original_filename . '"',
        ]);
    }

    /**
     * Dispatch document processing to the AI microservice.
     */
    protected function dispatchToAiService(Document $document, string $action): void
    {
        $client = new AiMicroserviceClient();
        $filePath = Storage::disk('local')->path($document->storage_path);

        // Update status to processing
        $document->update(['status' => 'processing']);

        DocumentLog::create([
            'document_id' => $document->id,
            'action' => 'processing',
            'details' => 'Dokumen dikirim ke AI Service untuk diproses.',
        ]);

        $result = $client->processDocument($document->id, $filePath, $action);

        if (!$result['success']) {
            // Log the failure but don't change status yet — the service might still process it async
            DocumentLog::create([
                'document_id' => $document->id,
                'action' => 'failed',
                'details' => $result['message'],
            ]);

            // If it's a connection error, revert to pending
            if ($result['data'] === null) {
                $document->update([
                    'status' => 'pending',
                    'error_message' => $result['message'],
                ]);
            }
        }
    }
}
