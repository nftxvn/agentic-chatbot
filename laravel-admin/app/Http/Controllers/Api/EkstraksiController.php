<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Models\DocumentLog;
use App\Models\EkstraksiHalaman;
use App\Models\EkstraksiJob;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

class EkstraksiController extends Controller
{
    protected AiMicroserviceClient $client;

    public function __construct(AiMicroserviceClient $client)
    {
        $this->client = $client;
    }

    /**
     * Start or resume staged OCR extraction.
     */
    public function mulai(int $id, Request $request): JsonResponse
    {
        $document = Document::with('category')->findOrFail($id);

        $maksHalaman = $request->input('maks_halaman') ? (int) $request->input('maks_halaman') : null;

        // Nama kolomnya harus persis seperti di tabel document_categories.
        // Sebelumnya baris pertama membaca `system_prompt` dan `job_titles` —
        // dua kolom yang TIDAK PERNAH ADA. Eloquent mengembalikan null, lalu
        // AiMicroserviceClient membuangnya karena kosong, sehingga prompt OCR
        // dan daftar jabatan tidak pernah sampai ke layanan Python. Tidak ada
        // galat yang muncul; ekstraksi hanya berjalan seolah kategorinya kosong.
        //
        // job_titles disimpan di dalam JSON `prompt_variables`
        // ({"job_titles": ["Kepala Dinas", ...]}), sedangkan sisi Python
        // mengharapkan teks biasa — jadi digabung di sini, bukan sekadar
        // diganti namanya. data_get() dipakai supaya kategori kosong, JSON
        // tanpa kunci itu, atau dokumen tanpa kategori sama-sama aman.
        // Kunci `kata_kunci` adalah nama barunya; `job_titles` dibaca sebagai
        // cadangan supaya kategori yang sudah terlanjur diisi tidak kehilangan
        // datanya. Isinya bukan cuma jabatan — singkatan seperti Renstra, RKA,
        // SPPD juga sering salah dibaca model vision dan pantas masuk daftar.
        $kataKunci = data_get($document->category, 'prompt_variables.kata_kunci')
            ?? data_get($document->category, 'prompt_variables.job_titles', []);
        $customPrompts = data_get($document->category, 'prompt_variables.custom_prompts', []);

        $categoryOptions = [
            'category_prompt' => $document->category?->vision_prompt,
            'job_titles'      => is_array($kataKunci) ? implode(', ', $kataKunci) : $kataKunci,
            'vision_model'    => $document->category?->vision_model,
            'custom_prompts'  => !empty($customPrompts) ? $customPrompts : null,
        ];

        $result = $this->client->mulaiEkstraksi($document->id, $maksHalaman, $categoryOptions);

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal memulai ekstraksi',
            ], $result['status'] ?? 500);
        }

        $document->update([
            'status'        => 'processing',
            'error_message' => null,
        ]);

        $document->recordLog('processing', 'Ekstraksi bertahap dimulai oleh ' . (Auth::user()?->name ?? 'Admin'), 15);

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

        // Also update MySQL flag directly to guarantee fast response
        $job = EkstraksiJob::where('document_id', $document->id)->first();
        if ($job && ($job->status === 'jeda' || $job->jeda_diminta)) {
            // Already paused or requested pause
            return response()->json([
                'success' => true,
                'message' => 'Permintaan jeda sudah diajukan sebelumnya.',
                'data'    => ['document_id' => $document->id, 'jeda_diminta' => true],
            ], 200);
        }

        EkstraksiJob::where('document_id', $document->id)->update(['jeda_diminta' => true]);

        $result = $this->client->jedaEkstraksi($document->id);

        $document->recordLog('paused', 'Ekstraksi dokumen dijeda oleh ' . (Auth::user()?->name ?? 'Admin'), 15);

        return response()->json([
            'success' => true,
            'message' => 'Permintaan jeda diterima. Ekstraksi akan berhenti di batas halaman.',
            'data'    => $result['data'] ?? ['document_id' => $document->id, 'jeda_diminta' => true],
        ], 202);
    }

    /**
     * Get current status and progress of staged extraction.
     */
    public function status(int $id): JsonResponse
    {
        $document = Document::findOrFail($id);

        // Try reading from MySQL table first for instant response
        $job = EkstraksiJob::where('document_id', $document->id)->first();

        if ($job) {
            return response()->json([
                'success' => true,
                'data'    => [
                    'document_id'     => $document->id,
                    'status'          => $job->status,
                    'jeda_diminta'    => (bool) $job->jeda_diminta,
                    'halaman_total'   => (int) $job->halaman_total,
                    'halaman_selesai' => (int) $job->halaman_selesai,
                    'persen'          => $job->persen,
                    'pesan'           => $job->pesan,
                ],
            ]);
        }

        // Fallback to Python AI endpoint
        $result = $this->client->statusEkstraksi($document->id);

        if ($result['success']) {
            return response()->json([
                'success' => true,
                'data'    => $result['data'],
            ]);
        }

        return response()->json([
            'success' => true,
            'data'    => [
                'document_id'     => $document->id,
                'status'          => 'antre',
                'jeda_diminta'    => false,
                'halaman_total'   => $document->total_pages ?? 0,
                'halaman_selesai' => 0,
                'persen'          => 0,
                'pesan'           => null,
            ],
        ]);
    }

    /**
     * List extracted page texts for correction editor.
     */
    public function halaman(int $id, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);
        $perluDiperiksa = $request->boolean('perlu_diperiksa');

        $result = $this->client->daftarHalaman($document->id, $perluDiperiksa);

        if ($result['success']) {
            return response()->json([
                'success' => true,
                'data'    => $result['data'],
            ]);
        }

        // Fallback to reading from local database
        $query = EkstraksiHalaman::where('document_id', $document->id)->orderBy('page_number');
        if ($perluDiperiksa) {
            $query->where('diperiksa', false);
        }

        $pages = $query->get(['page_number', 'text', 'diperiksa']);

        return response()->json([
            'success' => true,
            'data'    => [
                'document_id' => $document->id,
                'jumlah'      => $pages->count(),
                'halaman'     => $pages,
            ],
        ]);
    }

    /**
     * Save human text correction for a single page.
     */
    public function simpanHalaman(int $id, int $pageNumber, Request $request): JsonResponse
    {
        $document = Document::findOrFail($id);

        $request->validate([
            'text' => ['required', 'string'],
        ], [
            'text.required' => 'Teks halaman tidak boleh kosong.',
        ]);

        $text = $request->input('text');
        $result = $this->client->simpanKoreksiHalaman($document->id, $pageNumber, $text);

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal menyimpan koreksi.',
            ], $result['status'] ?? 400);
        }

        // Mark as checked in local table (atomic upsert on composite key)
        DB::table('ekstraksi_halaman')->upsert(
            [
                [
                    'document_id' => $document->id,
                    'page_number' => $pageNumber,
                    'text'        => $text,
                    'diperiksa'   => 1,
                ]
            ],
            ['document_id', 'page_number'],
            ['text', 'diperiksa']
        );

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

        return response($res->body(), 200, [
            'Content-Type'   => 'image/jpeg',
            'Cache-Control'  => 'public, max-age=31536000, immutable',
            'ETag'           => $res->header('ETag') ?? "\"{$document->id}-{$pageNumber}-{$zoom}\"",
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
        $result = $this->client->simpanKeKorpus($document->id, $request->all());

        if (!$result['success']) {
            return response()->json([
                'success' => false,
                'message' => $result['message'] ?? 'Gagal menyimpan ke korpus.',
            ], $result['status'] ?? 409);
        }

        $document->recordLog('completed', 'Dokumen difinalisasi dan disimpan ke korpus vektor oleh ' . (Auth::user()?->name ?? 'Admin'), 15);

        return response()->json([
            'success' => true,
            'message' => 'Dokumen berhasil diantrekan untuk embedding ke korpus.',
            'data'    => $result['data'],
        ], 202);
    }
}
