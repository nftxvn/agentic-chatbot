<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class AiMicroserviceClient
{
    /**
     * Base URL of the AI microservice.
     */
    protected string $baseUrl;

    /**
     * Bearer token for authentication.
     */
    protected string $token;

    /**
     * Create a new AiMicroserviceClient instance.
     */
    public function __construct()
    {
        $this->baseUrl = rtrim(config('services.ai_microservice.url', 'http://localhost:8080'), '/');
        $this->token = config('services.ai_microservice.token', '');
    }

    /**
     * Send a document for processing to the Python AI service.
     *
     * @param int    $documentId  The document ID in the database
     * @param string $filePath    Absolute path to the PDF file
     * @param string $action      Processing action: 'overwrite' or 'new'
     *
     * @return array{success: bool, message: string, data: mixed}
     */
    public function processDocument(int $documentId, string $filePath, string $action = 'overwrite'): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->connectTimeout(10)
                ->post("{$this->baseUrl}/api/docs/process", [
                    'document_id' => $documentId,
                    'file_path' => $filePath,
                    'action' => $action,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'message' => 'Dokumen berhasil dikirim untuk diproses.',
                    'data' => $response->json(),
                ];
            }

            Log::warning('AI Microservice returned error', [
                'status' => $response->status(),
                'body' => $response->body(),
                'document_id' => $documentId,
            ]);

            return [
                'success' => false,
                'message' => 'AI Service mengembalikan error: ' . $response->status(),
                'data' => $response->json(),
            ];
        } catch (\Illuminate\Http\Client\ConnectionException $e) {
            Log::error('AI Microservice connection failed', [
                'error' => $e->getMessage(),
                'document_id' => $documentId,
            ]);

            return [
                'success' => false,
                'message' => 'Tidak dapat terhubung ke AI Service. Pastikan service berjalan di ' . $this->baseUrl,
                'data' => null,
            ];
        } catch (\Exception $e) {
            Log::error('AI Microservice unexpected error', [
                'error' => $e->getMessage(),
                'document_id' => $documentId,
            ]);

            return [
                'success' => false,
                'message' => 'Terjadi kesalahan: ' . $e->getMessage(),
                'data' => null,
            ];
        }
    }

    /**
     * Check if the AI microservice is healthy/reachable.
     *
     * @return bool
     */
    public function healthCheck(): bool
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(5)
                ->connectTimeout(3)
                ->get("{$this->baseUrl}/health");

            return $response->successful();
        } catch (\Exception $e) {
            return false;
        }
    }

    /**
     * Get document chunks from ChromaDB via Python AI.
     */
    public function getDocumentChunks(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->get("{$this->baseUrl}/api/docs/{$documentId}/chunks");

            if ($response->successful()) {
                return $response->json();
            }
            return [];
        } catch (\Exception $e) {
            Log::error('Failed to get chunks', ['error' => $e->getMessage()]);
            return [];
        }
    }
}
