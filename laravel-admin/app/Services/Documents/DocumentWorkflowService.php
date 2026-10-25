<?php

namespace App\Services\Documents;

use App\Models\Document;
use App\Models\User;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class DocumentWorkflowService
{
    public const AI_UNAVAILABLE_MESSAGE = 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.';

    public function __construct(
        private AiMicroserviceClient $client,
        private DocumentCategoryOptions $categoryOptions,
    ) {
    }

    public function upload(UploadedFile $file, string $title, ?int $categoryId, User $actor): DocumentUploadResult
    {
        $stored = $this->storeFile($file);
        $document = Document::create([
            'title' => strip_tags(trim($title)),
            'original_name' => $stored['original_name'],
            'file_path' => $stored['file_path'],
            'status' => 'pending',
            'pdf_type' => 'unknown',
            'category_id' => $categoryId,
            'uploaded_by' => $actor->id,
        ]);

        $document->recordLog('uploaded', "File \"{$stored['original_name']}\" diunggah oleh {$actor->name}");

        if (!$this->client->healthCheck()) {
            $this->markAiUnavailable($document);

            return new DocumentUploadResult($document, false);
        }

        $this->dispatch($document);

        return new DocumentUploadResult($document, true);
    }

    public function replace(Document $document, UploadedFile $file, ?User $actor): void
    {
        $this->requestCancellation($document, cleanupDocument: true);
        $this->client->cancelDocument($document->id);
        $this->deleteFile($document);
        $this->clearExtraction($document);
        $this->client->deleteDocument($document->id);

        $stored = $this->storeFile($file);
        $document->update([
            'original_name' => $stored['original_name'],
            'file_path' => $stored['file_path'],
            'status' => 'pending',
            'pdf_type' => 'unknown',
            'error_message' => null,
            'total_pages' => null,
            'processed_pages' => 0,
            'total_chunks' => null,
            'processed_at' => null,
        ]);

        $document->recordLog('replaced', "File diganti dengan \"{$stored['original_name']}\" oleh " . ($actor?->name ?? 'Admin'));
        $this->dispatch($document);
    }

    public function cancel(Document $document, ?User $actor): void
    {
        $this->requestCancellation($document, 'Pemrosesan dibatalkan oleh Admin.');
        $document->recordLog('cancelled', 'Pemrosesan AI dibatalkan oleh ' . ($actor?->name ?? 'Admin') . '.', 15);
        $this->client->cancelDocument($document->id);
    }

    /**
     * Health determines the HTTP outcome; the existing resume path ignores queue rejection.
     */
    public function resume(Document $document, ?User $actor): bool
    {
        if (!$this->client->healthCheck()) {
            $this->markAiUnavailable($document);

            return false;
        }

        $document->update(['status' => 'processing', 'error_message' => null]);
        $document->recordLog('resumed', 'Ekstraksi AI dilanjutkan kembali oleh ' . ($actor?->name ?? 'Admin') . '.', 15);
        $this->client->mulaiEkstraksi($document->id, null, $this->categoryOptions->forDocument($document));

        return true;
    }

    public function delete(Document $document): void
    {
        $this->requestCancellation($document, cleanupDocument: true);
        $this->deleteFile($document);
        $this->client->cancelDocument($document->id);
        $this->client->deleteDocument($document->id);
        $this->clearExtraction($document);
        $document->delete();
    }

    private function requestCancellation(Document $document, ?string $message = null, bool $cleanupDocument = false): void
    {
        // Persist the fence before HTTP: a disconnected AI service must not let
        // its worker overwrite a cancellation or a replacement/deletion.
        DB::transaction(function () use ($document, $message, $cleanupDocument): void {
            $current = Document::query()->lockForUpdate()->findOrFail($document->id);
            $completed = $current->status === 'completed' || $current->processed_at !== null;
            $token = $cleanupDocument ? '' : ($completed ? null : $current->processing_token);
            if ($token !== null && ($cleanupDocument || $token !== '')) {
                $cleanup = DB::table('document_vector_cleanups')
                    ->where('document_id', $current->id)->where('operation_token', $token);
                if (!$cleanup->exists()) {
                    DB::table('document_vector_cleanups')->insert([
                        'document_id' => $current->id,
                        'operation_token' => $token,
                        'attempts' => 0,
                        'available_at' => now('UTC'),
                        'created_at' => now('UTC'),
                        'updated_at' => now('UTC'),
                    ]);
                }
            }
            $changes = ['cancellation_requested' => true];
            if ($message !== null) {
                $changes += ['status' => 'failed', 'error_message' => $message];
            }
            $current->forceFill($changes)->save();
            $document->setRawAttributes($current->getAttributes(), true);
            DB::table('ekstraksi_job')->where('document_id', $document->id)->update([
                'status' => 'gagal',
                'jeda_diminta' => false,
                'pesan' => $message ?? 'Operasi dokumen dibatalkan.',
            ]);
        });
    }

    private function dispatch(Document $document): void
    {
        $document->update(['status' => 'processing', 'error_message' => null]);
        $document->recordLog('processing', 'Dokumen dikirim ke antrean Ekstraksi AI bertahap.', 15);
        $result = $this->client->mulaiEkstraksi($document->id, null, $this->categoryOptions->forDocument($document));

        if (!$result['success']) {
            $message = $result['message'] ?? 'Gagal memulai ekstraksi';
            $document->recordLog('failed', $message, 10);
            $document->update(['status' => 'pending', 'error_message' => $message]);
        }
    }

    private function markAiUnavailable(Document $document): void
    {
        $document->update(['status' => 'failed', 'error_message' => self::AI_UNAVAILABLE_MESSAGE]);
    }

    /** @return array{original_name: string, file_path: string} */
    private function storeFile(UploadedFile $file): array
    {
        $originalFilename = preg_replace('/[^\w\s\-\.\(\)\[\]]/u', '_', basename($file->getClientOriginalName()));
        $extension = strtolower($file->getClientOriginalExtension() ?: $file->extension() ?: 'bin');
        $hashedName = hash('sha256', Str::uuid()->toString() . microtime(true) . $file->getContent()) . '.' . $extension;
        $storagePath = $file->storeAs('documents', $hashedName, 'local');

        return [
            'original_name' => $originalFilename,
            'file_path' => Storage::disk('local')->path($storagePath),
        ];
    }

    private function deleteFile(Document $document): void
    {
        $filePath = $document->file_path ?? Storage::disk('local')->path($document->storage_path ?? '');
        if ($filePath && file_exists($filePath)) {
            @unlink($filePath);
        }
    }

    private function clearExtraction(Document $document): void
    {
        DB::table('ekstraksi_halaman')->where('document_id', $document->id)->delete();
        DB::table('ekstraksi_job')->where('document_id', $document->id)->delete();
    }
}
