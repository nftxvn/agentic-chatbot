<?php

namespace App\Services\Ai;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Health, pembatalan, dan operasi vektor dokumen.
 *
 * Dipakai AiMicroserviceClient agar konfigurasi URL/token dan formatter error
 * tetap berasal dari instance yang sama, termasuk override pada subclass.
 *
 * @mixin \App\Services\AiMicroserviceClient
 */
trait DocumentRequests
{
    abstract protected function extractErrorMessage($response, string $fallback = 'Terjadi kesalahan pada AI service'): string;

    /**
     * Check if the AI microservice is healthy/reachable.
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
     * Cancel an active document processing and release system resources.
     */
    public function cancelDocument(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(10)
                ->connectTimeout(5)
                ->post("{$this->baseUrl}/api/docs/{$documentId}/cancel");

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal membatalkan di AI service'),
            ];
        } catch (\Exception $e) {
            return [
                'success' => false,
                'message' => 'Tidak dapat terhubung ke AI service: ' . $e->getMessage(),
            ];
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
        } catch (\Exception $e) {
            Log::error('Failed to get chunks', ['error' => $e->getMessage()]);
            return [];
        }

        return [];
    }

    /**
     * Get total active vector counts grouped by document_id from ChromaDB.
     */
    public function getVectorCounts(): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(10)
                ->get("{$this->baseUrl}/api/docs/vector-counts");

            if ($response->successful()) {
                return $response->json('counts', []);
            }
        } catch (\Exception $e) {
            Log::warning('Failed to get vector counts from ChromaDB', ['error' => $e->getMessage()]);
        }
        return [];
    }

    /**
     * Delete document vectors from ChromaDB via Python AI.
     */
    public function deleteDocument(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(15)
                ->delete("{$this->baseUrl}/api/docs/{$documentId}");

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal menghapus vektor dokumen'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Failed to delete document vectors', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }
}
