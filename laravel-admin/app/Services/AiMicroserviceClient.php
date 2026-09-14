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
     * Send a document for full processing pipeline (legacy/batch process).
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
                    'file_path'   => $filePath,
                    'action'      => $action,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'message' => 'Dokumen berhasil dikirim untuk diproses.',
                    'data'    => $response->json(),
                ];
            }

            Log::warning('AI Microservice returned error on processDocument', [
                'status'      => $response->status(),
                'body'        => $response->body(),
                'document_id' => $documentId,
            ]);

            return [
                'success' => false,
                'message' => 'AI Service mengembalikan error: ' . $response->status(),
                'data'    => $response->json(),
            ];
        } catch (\Exception $e) {
            Log::error('AI Microservice connection failed on processDocument', [
                'error'       => $e->getMessage(),
                'document_id' => $documentId,
            ]);

            return [
                'success' => false,
                'message' => 'Tidak dapat terhubung ke AI Service: ' . $e->getMessage(),
                'data'    => null,
            ];
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

    // ── STAGED EXTRACTION APIS (Ekstraksi Bertahap) ─────────────────

    /**
     * Start or resume staged OCR extraction.
     */
    public function mulaiEkstraksi(int $documentId, ?int $maksHalaman = null, array $categoryOptions = []): array
    {
        try {
            $payload = [];
            if ($maksHalaman !== null) {
                $payload['maks_halaman'] = $maksHalaman;
            }
            // Nilai kosong sengaja tidak dikirim supaya Python memakai
            // bawaannya. Tapi HANYA yang kosong — kalau seluruh setelan
            // kategori raib padahal kategorinya ada, itu tanda rantainya putus,
            // bukan tanda kategorinya memang kosong.
            //
            // Penjaga di bawah lahir dari bug nyata: selama berbulan-bulan
            // `category_prompt` dan `job_titles` selalu null karena controller
            // membaca nama kolom yang salah, dan tidak ada satu pun pesan yang
            // muncul. Baris log ini membuat kegagalan sejenis ketahuan dalam
            // hitungan menit.
            foreach (['category_prompt', 'job_titles', 'vision_model', 'custom_prompts'] as $kunci) {
                if (!empty($categoryOptions[$kunci])) {
                    $payload[$kunci] = $categoryOptions[$kunci];
                }
            }

            if (!empty($categoryOptions) && empty(array_filter($categoryOptions))) {
                Log::warning('Setelan kategori tidak sampai ke layanan AI — seluruh nilainya kosong.', [
                    'document_id' => $documentId,
                    'kunci_dikirim' => array_keys($categoryOptions),
                    'petunjuk' => 'Periksa nama kolom di EkstraksiController terhadap tabel document_categories.',
                ]);
            }

            $response = Http::withToken($this->token)
                ->timeout(30)
                ->connectTimeout(10)
                ->post("{$this->baseUrl}/api/docs/{$documentId}/ekstraksi", !empty($payload) ? $payload : (object)[]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal memulai ekstraksi'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling mulaiEkstraksi', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Request pause for staged extraction.
     */
    public function jedaEkstraksi(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(15)
                ->connectTimeout(5)
                ->post("{$this->baseUrl}/api/docs/{$documentId}/ekstraksi/jeda");

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal meminta jeda'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling jedaEkstraksi', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Get current status of staged extraction.
     */
    public function statusEkstraksi(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(15)
                ->get("{$this->baseUrl}/api/docs/{$documentId}/ekstraksi");

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal membaca status ekstraksi'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling statusEkstraksi', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Get extracted text of pages for correction editor.
     */
    public function daftarHalaman(int $documentId, bool $perluDiperiksa = false): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->get("{$this->baseUrl}/api/docs/{$documentId}/halaman", [
                    'perlu_diperiksa' => $perluDiperiksa ? 1 : 0,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal memuat teks halaman'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling daftarHalaman', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Save human correction for a specific page.
     */
    public function simpanKoreksiHalaman(int $documentId, int $pageNumber, string $text): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->put("{$this->baseUrl}/api/docs/{$documentId}/halaman/{$pageNumber}", [
                    'text' => $text,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal menyimpan koreksi halaman'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling simpanKoreksiHalaman', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Get page dimensions without rendering image.
     */
    public function ukuranHalaman(int $documentId): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(15)
                ->get("{$this->baseUrl}/api/docs/{$documentId}/halaman/ukuran");

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal mengambil ukuran halaman'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling ukuranHalaman', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Fetch rendered JPEG image of a specific page.
     */
    public function citraHalaman(int $documentId, int $pageNumber, float $zoom = 2.0): ?\Illuminate\Http\Client\Response
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->get("{$this->baseUrl}/api/docs/{$documentId}/halaman/{$pageNumber}/citra", [
                    'zoom' => $zoom,
                ]);

            if ($response->successful()) {
                return $response;
            }

            return null;
        } catch (\Exception $e) {
            Log::error('Error calling citraHalaman', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return null;
        }
    }

    /**
     * Preview parent and child chunks without saving.
     */
    public function pratinjauPotongan(int $documentId, array $params = []): array
    {
        try {
            $req = Http::withToken($this->token)->timeout(30);
            if (!empty($params)) {
                $response = $req->post("{$this->baseUrl}/api/docs/{$documentId}/potongan", $params);
            } else {
                $response = $req->get("{$this->baseUrl}/api/docs/{$documentId}/potongan");
            }

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal membuat pratinjau potongan'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling pratinjauPotongan', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Finalize document: chunk text and embed vectors to ChromaDB.
     */
    public function simpanKeKorpus(int $documentId, array $params = []): array
    {
        try {
            $response = Http::withToken($this->token)
                ->timeout(30)
                ->connectTimeout(10)
                ->post("{$this->baseUrl}/api/docs/{$documentId}/simpan", !empty($params) ? $params : (object)[]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data'    => $response->json(),
                ];
            }

            return [
                'success' => false,
                'message' => $this->extractErrorMessage($response, 'Gagal menyimpan ke korpus'),
                'status'  => $response->status(),
            ];
        } catch (\Exception $e) {
            Log::error('Error calling simpanKeKorpus', ['error' => $e->getMessage(), 'document_id' => $documentId]);
            return ['success' => false, 'message' => $e->getMessage()];
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

    /**
     * Safely format error message from HTTP response (handles string, array, or null).
     */
    protected function extractErrorMessage($response, string $fallback = 'Terjadi kesalahan pada AI service'): string
    {
        $detail = $response->json('detail');
        if (is_string($detail) && trim($detail) !== '') {
            return $detail;
        }
        if (is_array($detail)) {
            $messages = [];
            foreach ($detail as $err) {
                if (is_array($err) && isset($err['msg'])) {
                    $field = isset($err['loc']) ? implode('.', (array)$err['loc']) . ': ' : '';
                    $messages[] = $field . $err['msg'];
                } else if (is_string($err)) {
                    $messages[] = $err;
                }
            }
            if (!empty($messages)) {
                return implode(', ', $messages);
            }
            return json_encode($detail, JSON_UNESCAPED_UNICODE);
        }
        return $fallback . ' (HTTP ' . $response->status() . ')';
    }
}
