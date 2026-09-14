<?php

namespace App\Http\Controllers;

use App\Models\Document;
use App\Models\DocumentLog;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

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
     * Handle a new document upload.
     */
    public function upload(Request $request)
    {
        $request->validate([
            'title'    => ['required', 'string', 'max:255'],
            'pdf_file' => ['required', 'file', 'mimes:pdf,docx,xlsx,csv,txt,md', 'max:51200'], // Max 50MB
        ], [
            'title.required'    => 'Judul dokumen wajib diisi.',
            'title.max'         => 'Judul dokumen maksimal 255 karakter.',
            'pdf_file.required' => 'File dokumen wajib diunggah.',
            'pdf_file.mimes'    => 'Format file tidak diizinkan. Gunakan format: PDF, DOCX, XLSX, CSV, TXT, atau MD.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        $file             = $request->file('pdf_file');
        $rawFilename      = $file->getClientOriginalName();
        $originalFilename = preg_replace('/[^\w\s\-\.\(\)\[\]]/u', '_', basename($rawFilename));
        $sanitizedTitle   = strip_tags(trim($request->input('title')));

        // Generate a secure random hashed filename (SHA-256)
        $extension        = strtolower($file->getClientOriginalExtension() ?: $file->extension() ?: 'bin');
        $hashedName       = hash('sha256', Str::uuid()->toString() . microtime(true) . $file->getContent()) . '.' . $extension;
        $storagePath      = $file->storeAs('documents', $hashedName, 'local');

        // Create the document record
        $document = Document::create([
            'title'             => $sanitizedTitle,
            'original_filename' => $originalFilename,
            'storage_path'      => $storagePath,
            'status'            => 'pending',
            'pdf_type'          => 'unknown',
            'uploaded_by'       => Auth::id(),
        ]);

        // Log the upload
        $document->recordLog('uploaded', "File \"{$originalFilename}\" diunggah oleh " . Auth::user()->name);

        // Dispatch processing to AI microservice
        $this->dispatchToAiService($document, 'new');

        return redirect()
            ->route('documents.show', $document->id)
            ->with('success', "Dokumen \"{$document->title}\" berhasil diunggah dan sedang diproses.");
    }

    /**
     * Handle replacing an existing document's file.
     */
    public function replace(int $id, Request $request)
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'pdf_file' => ['required', 'file', 'mimes:pdf,docx,xlsx,csv,txt,md', 'max:51200'],
        ], [
            'pdf_file.required' => 'File dokumen wajib diunggah.',
            'pdf_file.mimes'    => 'Format file tidak diizinkan. Gunakan format: PDF, DOCX, XLSX, CSV, TXT, atau MD.',
            'pdf_file.max'      => 'Ukuran file maksimal 50MB.',
        ]);

        // Delete the old file
        if (Storage::disk('local')->exists($document->storage_path)) {
            Storage::disk('local')->delete($document->storage_path);
        }

        $file             = $request->file('pdf_file');
        $rawFilename      = $file->getClientOriginalName();
        $originalFilename = preg_replace('/[^\w\s\-\.\(\)\[\]]/u', '_', basename($rawFilename));

        // Generate a secure random hashed filename (SHA-256)
        $extension        = strtolower($file->getClientOriginalExtension() ?: $file->extension() ?: 'bin');
        $hashedName       = hash('sha256', Str::uuid()->toString() . microtime(true) . $file->getContent()) . '.' . $extension;
        $storagePath      = $file->storeAs('documents', $hashedName, 'local');

        // Update the document record
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

        // Log the replacement
        $document->recordLog('replaced', "File diganti dengan \"{$originalFilename}\" oleh " . Auth::user()->name);

        // Dispatch processing to AI microservice with overwrite action
        $this->dispatchToAiService($document, 'overwrite');

        return redirect()
            ->route('documents.show', $document->id)
            ->with('success', 'File dokumen berhasil diganti dan sedang diproses ulang.');
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

        // Delete the document record (cascade deletes logs)
        $document->delete();

        return redirect()
            ->route('documents.index')
            ->with('success', 'Dokumen berhasil dihapus.');
    }

    /**
     * Serve the document file for preview/download.
     */
    public function servePdf(int $id)
    {
        $document = Document::findOrFail($id);

        $filePath = Storage::disk('local')->path($document->storage_path);

        if (!file_exists($filePath)) {
            abort(404, 'File dokumen tidak ditemukan.');
        }

        $mimeType = @mime_content_type($filePath) ?: 'application/octet-stream';
        $filename = $document->original_filename ?? 'document';

        return response()->file($filePath, [
            'Content-Type'        => $mimeType,
            'Content-Disposition' => 'inline; filename="' . addslashes($filename) . '"',
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

        $document->recordLog('processing', 'Dokumen dikirim ke AI Service untuk diproses.', 15);

        $result = $client->processDocument($document->id, $filePath, $action);

        if (!$result['success']) {
            // Log the failure but don't change status yet — the service might still process it async
            $document->recordLog('failed', $result['message'], 10);

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
