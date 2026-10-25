<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Services\AiMicroserviceClient;
use App\Services\Documents\DocumentExtractionService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Str;

class EkstraksiController extends Controller
{
    public function __construct(
        protected AiMicroserviceClient $client,
        private DocumentExtractionService $extraction,
    ) {
    }

    /**
     * Start or resume staged OCR extraction.
     */
    public function mulai(int $id, Request $request): JsonResponse
    {
        $document = Document::with('category')->findOrFail($id);

        $maksHalaman = $request->input('maks_halaman') ? (int) $request->input('maks_halaman') : null;

        $result = $this->extraction->start($document, $maksHalaman, Auth::user());

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal memulai ekstraksi',
            ], $result['status'] ?? 500);
        }

        return response()->json([
            'success' => true,
            'message' => 'Ekstraksi dokumen diantrekan.',
            'data'    => $result['data'],
        ], 202);
    }

    /**
     * Request pause for staged extraction at the next page boundary.
     */
    public function jeda(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        $result = $this->extraction->pause($document, Auth::user());

        return response()->json([
            'success' => true,
            'message' => $result['already_requested']
                ? 'Permintaan jeda sudah diajukan sebelumnya.'
                : 'Permintaan jeda diterima. Ekstraksi akan berhenti di batas halaman.',
            'data' => $result['data'],
        ], $result['already_requested'] ? 200 : 202);
    }

    /**
     * Get current status and progress of staged extraction.
     */
    public function status(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);

        return response()->json([
            'success' => true,
            'data' => $this->extraction->status($document),
        ]);
    }

    /**
     * List extracted page texts for correction editor.
     */
    public function halaman(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);

        return response()->json([
            'success' => true,
            'data' => $this->extraction->pages($document, $request->boolean('perlu_diperiksa')),
        ]);
    }

    /**
     * Save human text correction for a single page.
     */
    public function simpanHalaman(int $id, int $pageNumber, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'text' => [
                'required',
                'string',
                function (string $attribute, mixed $value, \Closure $fail): void {
                    if (is_string($value) && Str::trim($value) === '') {
                        $fail('Teks halaman tidak boleh kosong.');
                    }
                },
            ],
        ], [
            'text.required' => 'Teks halaman tidak boleh kosong.',
        ]);

        $text = $request->input('text');
        $result = $this->extraction->saveCorrection($document, $pageNumber, $text);

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal menyimpan koreksi.',
            ], $result['status'] ?? 400);
        }

        return response()->json([
            'success' => true,
            'message' => "Halaman {$pageNumber} berhasil dikoreksi.",
            'data'    => $result['data'],
        ]);
    }

    /**
     * Get dimensions and orientations of all pages.
     */
    public function ukuranHalaman(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);
        $result = $this->client->ukuranHalaman($document->id);

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal mengambil ukuran halaman.',
            ], $result['status'] ?? 500);
        }

        return response()->json([
            'success' => true,
            'data'    => $result['data'],
        ]);
    }

    /**
     * Stream or return rendered JPEG page image.
     */
    public function citraHalaman(int $id, int $pageNumber, Request $request): Response|JsonResponse
    {
        $document = Document::findOrFail($id);
        $zoom = (float) $request->input('zoom', 2.0);

        $res = $this->client->citraHalaman($document->id, $pageNumber, $zoom);

        if (!$res || !$res->successful()) {
            return response()->json([
                'success' => false,
                'message' => 'Citra halaman tidak ditemukan.',
            ], 404);
        }

        $mtime = file_exists($document->file_path ?? '') ? @filemtime($document->file_path) : time();

        return response($res->body(), 200, [
            'Content-Type'   => 'image/jpeg',
            'Cache-Control'  => 'public, max-age=31536000, immutable',
            'ETag'           => $res->header('ETag') ?? "\"{$document->id}-{$pageNumber}-{$zoom}-{$mtime}\"",
            'X-Lebar-Piksel' => $res->header('X-Lebar-Piksel') ?? '',
            'X-Tinggi-Piksel'=> $res->header('X-Tinggi-Piksel') ?? '',
        ]);
    }

    /**
     * Preview parent and child chunks.
     */
    public function potongan(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);
        $result = $this->client->pratinjauPotongan($document->id, $request->all());

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal mengambil pratinjau potongan.',
            ], $result['status'] ?? 500);
        }

        return response()->json([
            'success' => true,
            'data'    => $result['data'],
        ]);
    }

    /**
     * Finalize document: chunk text and store embeddings into ChromaDB.
     */
    public function simpanKorpus(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);
        $result = $this->extraction->embed($document, $request->all(), Auth::user());

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal menyimpan ke korpus.',
            ], $result['status'] ?? 409);
        }

        return response()->json([
            'success' => true,
            'message' => 'Dokumen berhasil diantrekan untuk embedding ke korpus.',
            'data'    => $result['data'],
        ], 202);
    }
}
