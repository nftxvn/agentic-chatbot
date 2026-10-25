<?php

namespace Tests\Feature;

use App\Models\Document;
use App\Models\DocumentCategory;
use App\Models\EkstraksiHalaman;
use App\Models\EkstraksiJob;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class DocumentPipelineContractTest extends TestCase
{
    use RefreshDatabase;

    private User $admin;

    private const AI = 'http://ai.example.test';

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'services.ai_microservice.url' => self::AI,
            'services.ai_microservice.token' => 'document-contract-token',
        ]);
        Storage::fake('local');
        Http::preventStrayRequests();
        $this->admin = User::factory()->create(['name' => 'Admin Dokumen']);
        $this->actingAs($this->admin);
    }

    public function test_listing_preserves_dashboard_fields_and_progress(): void
    {
        $document = $this->document(['status' => 'processing', 'total_pages' => 3, 'processed_pages' => 2]);
        EkstraksiJob::create([
            'document_id' => $document->id,
            'status' => 'berjalan',
            'halaman_total' => 100,
            'halaman_selesai' => 90,
        ]);
        $this->page($document, 1);
        $this->page($document, 2);
        $this->fakeAi();

        $response = $this->getJson('/api/documents')->assertOk();
        $response->assertJsonStructure(['success', 'data' => [
            'documents' => [[
                'id', 'title', 'original_filename', 'original_name', 'file_path',
                'status', 'status_label', 'pdf_type', 'pdf_type_label', 'category_id',
                'category_name', 'category_ui_layout', 'total_pages', 'processed_pages',
                'total_chunks', 'vector_count', 'error_message', 'uploaded_by', 'pdf_url',
                'created_at', 'updated_at', 'processed_at', 'ekstraksi_status',
                'jeda_diminta', 'halaman_selesai', 'persen_ekstraksi',
            ]],
            'meta', 'stats', 'has_processing',
        ]]);
        $response->assertJsonPath('data.documents.0.status_label', 'Memproses')
            ->assertJsonPath('data.documents.0.total_pages', 3)
            ->assertJsonPath('data.documents.0.processed_pages', 2)
            ->assertJsonPath('data.documents.0.persen_ekstraksi', 67)
            ->assertJsonPath('data.documents.0.original_filename', 'source.txt')
            ->assertJsonPath('data.documents.0.original_name', 'source.txt')
            ->assertJsonPath('data.documents.0.uploaded_by', 'Admin Dokumen')
            ->assertJsonPath('data.stats', [
                'total' => 1, 'completed' => 0, 'menunggu_koreksi' => 0, 'processing' => 1, 'failed' => 0,
            ])->assertJsonPath('data.has_processing', true);
    }

    public function test_completed_document_synchronizes_live_vector_count(): void
    {
        $document = $this->document(['status' => 'completed', 'total_chunks' => 99]);
        $this->fakeAi([
            self::AI.'/api/docs/vector-counts' => Http::response(['counts' => [$document->id => 7]]),
        ]);

        $this->getJson("/api/documents/{$document->id}")->assertOk()
            ->assertJsonPath('data.document.status_label', 'Selesai')
            ->assertJsonPath('data.document.total_chunks', 7)
            ->assertJsonPath('data.document.vector_count', 7)
            ->assertJsonPath('data.document.logs', []);
        $this->assertSame(7, $document->fresh()->total_chunks);
    }

    #[DataProvider('statusPresentationCases')]
    public function test_status_precedence_keeps_existing_dashboard_labels(
        string $documentStatus,
        ?string $jobStatus,
        bool $pauseRequested,
        int $processed,
        string $expectedStatus,
        string $expectedLabel,
    ): void {
        $document = $this->document(['status' => $documentStatus, 'total_pages' => 2, 'processed_pages' => $processed]);
        if ($jobStatus !== null) {
            EkstraksiJob::create([
                'document_id' => $document->id, 'status' => $jobStatus, 'jeda_diminta' => $pauseRequested,
            ]);
        }
        $this->fakeAi();

        $this->getJson("/api/documents/{$document->id}")->assertOk()
            ->assertJsonPath('data.document.status', $expectedStatus)
            ->assertJsonPath('data.document.status_label', $expectedLabel);
    }

    public static function statusPresentationCases(): array
    {
        return [
            'completed document wins' => ['completed', 'gagal', false, 0, 'completed', 'Selesai'],
            'completed job wins' => ['failed', 'selesai', false, 0, 'completed', 'Selesai'],
            'awaiting review' => ['processing', 'menunggu_koreksi', false, 0, 'menunggu_koreksi', 'Menunggu Verifikasi'],
            'pausing processing' => ['processing', 'jeda', true, 0, 'processing', 'Menjeda...'],
            'live job wins over old failure' => ['failed', 'berjalan', false, 0, 'processing', 'Memproses'],
            'paused document' => ['paused', null, false, 0, 'jeda', 'Dijeda'],
            'finished pages await review' => ['pending', null, false, 2, 'menunggu_koreksi', 'Menunggu Verifikasi'],
            'failed job prevents review inference' => ['failed', 'gagal', false, 2, 'failed', 'Gagal'],
        ];
    }

    public function test_upload_sanitizes_file_and_forwards_category_options(): void
    {
        $category = DocumentCategory::create([
            'name' => 'SOP',
            'vision_prompt' => 'Baca tabel SOP.',
            'vision_model' => 'test-vision',
            'prompt_variables' => [
                'kata_kunci' => ['Renstra', 'SPPD'],
                'job_titles' => ['Legacy ignored'],
                'custom_prompts' => ['table' => 'Pertahankan kolom.'],
            ],
        ]);
        $this->fakeAi([self::AI.'/api/docs/*/extraction' => Http::response(['status' => 'antre'], 202)]);

        $response = $this->post('/api/documents', [
            'title' => '<b>SOP Pelayanan</b>',
            'category_id' => $category->id,
            'pdf_file' => UploadedFile::fake()->createWithContent('sop<>.txt', 'Isi SOP'),
        ])->assertCreated()->assertJsonPath('data.document.title', 'SOP Pelayanan')
            ->assertJsonPath('data.document.original_name', 'sop__.txt')
            ->assertJsonPath('data.document.status', 'processing');

        $document = Document::findOrFail($response->json('data.document.id'));
        $this->assertMatchesRegularExpression('/^[a-f0-9]{64}\.txt$/', basename($document->file_path));
        $this->assertSame('Isi SOP', file_get_contents($document->file_path));
        Http::assertSent(function (Request $request) use ($document) {
            return $request->url() === self::AI."/api/docs/{$document->id}/extraction"
                && $request->hasHeader('Authorization', 'Bearer document-contract-token')
                && $request->data() === [
                    'category_prompt' => 'Baca tabel SOP.',
                    'job_titles' => 'Renstra, SPPD',
                    'vision_model' => 'test-vision',
                    'custom_prompts' => ['table' => 'Pertahankan kolom.'],
                ];
        });
    }

    public function test_offline_upload_returns_503_and_keeps_failed_document(): void
    {
        $this->fakeAi([self::AI.'/health' => Http::response([], 503)]);

        $response = $this->post('/api/documents', [
            'title' => 'SOP Offline',
            'pdf_file' => UploadedFile::fake()->createWithContent('sop.txt', 'Isi SOP'),
        ])->assertStatus(503)->assertJsonPath('success', false)
            ->assertJsonPath('data.document.status', 'failed');

        $document = Document::findOrFail($response->json('data.document.id'));
        $this->assertFileExists($document->file_path);
        $this->assertSame($response->json('message'), $document->error_message);
        Http::assertSentCount(1);
    }

    public function test_rejected_queue_keeps_upload_response_and_pending_status(): void
    {
        $this->fakeAi([
            self::AI.'/api/docs/*/extraction' => Http::response(['detail' => 'Antrean tidak tersedia'], 422),
        ]);

        $response = $this->post('/api/documents', [
            'title' => 'SOP Antre',
            'pdf_file' => UploadedFile::fake()->createWithContent('sop.txt', 'Isi SOP'),
        ])->assertCreated()->assertJsonPath('success', true)
            ->assertJsonPath('data.document.status', 'pending')
            ->assertJsonPath('data.document.error_message', 'Antrean tidak tersedia');
        $this->assertDatabaseHas('document_logs', [
            'document_id' => $response->json('data.document.id'),
            'action' => 'failed',
        ]);
    }

    public function test_replacement_resets_old_extraction_before_restarting(): void
    {
        $document = $this->document([
            'status' => 'completed', 'total_pages' => 2, 'processed_pages' => 2,
            'total_chunks' => 12, 'processed_at' => now(),
        ]);
        $oldPath = $document->file_path;
        $this->page($document, 1);
        EkstraksiJob::create(['document_id' => $document->id, 'status' => 'selesai']);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/cancel" => Http::response([]),
            self::AI."/api/docs/{$document->id}" => Http::response([]),
            self::AI."/api/docs/{$document->id}/extraction" => Http::response(['status' => 'antre'], 202),
        ]);

        $this->post("/api/documents/{$document->id}/replace", [
            'pdf_file' => UploadedFile::fake()->createWithContent('replacement.txt', 'Revisi SOP'),
        ])->assertOk()->assertJsonPath('data.document.status', 'processing')
            ->assertJsonPath('data.document.original_name', 'replacement.txt');

        $this->assertFileDoesNotExist($oldPath);
        $document->refresh();
        $this->assertSame('Revisi SOP', file_get_contents($document->file_path));
        $this->assertNull($document->total_pages);
        $this->assertNull($document->total_chunks);
        $this->assertNull($document->processed_at);
        $this->assertSame(0, $document->processed_pages);
        $this->assertDatabaseCount('ekstraksi_halaman', 0);
        $this->assertDatabaseCount('ekstraksi_job', 0);
        Http::assertSentInOrder([
            fn (Request $request) => $request->method() === 'POST' && str_ends_with($request->url(), '/cancel'),
            fn (Request $request) => $request->method() === 'DELETE',
            fn (Request $request) => $request->method() === 'POST' && str_ends_with($request->url(), '/extraction'),
        ]);
    }

    public function test_cancel_keeps_existing_failed_status_and_audit_message(): void
    {
        $document = $this->document(['status' => 'processing']);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/cancel" => Http::response([])]);

        $this->postJson("/api/documents/{$document->id}/cancel")->assertOk()
            ->assertJsonPath('data.document.status', 'failed')
            ->assertJsonPath('data.document.status_label', 'Gagal')
            ->assertJsonPath('data.document.error_message', 'Pemrosesan dibatalkan oleh Admin.');
        $this->assertDatabaseHas('document_logs', ['document_id' => $document->id, 'action' => 'cancelled']);
        Http::assertSentCount(1);
    }

    public function test_resume_forwards_legacy_keywords_and_keeps_existing_queue_failure_behavior(): void
    {
        $category = DocumentCategory::create([
            'name' => 'Legacy', 'prompt_variables' => ['job_titles' => ['Kepala Dinas', 'Sekretaris']],
        ]);
        $document = $this->document(['status' => 'failed', 'category_id' => $category->id]);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/extraction" => Http::response(['detail' => 'Belum siap'], 503),
        ]);

        $this->postJson("/api/documents/{$document->id}/resume")->assertOk()
            ->assertJsonPath('success', true)->assertJsonPath('data.document.status', 'processing')
            ->assertJsonPath('data.document.error_message', null);
        Http::assertSent(fn (Request $request) => $request->data() === ['job_titles' => 'Kepala Dinas, Sekretaris']);
        $this->assertDatabaseHas('document_logs', ['document_id' => $document->id, 'action' => 'resumed']);
    }

    public function test_delete_cleans_local_data_even_when_ai_returns_errors(): void
    {
        $document = $this->document();
        $this->page($document, 1);
        EkstraksiJob::create(['document_id' => $document->id]);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/cancel" => Http::response([], 503),
            self::AI."/api/docs/{$document->id}" => Http::response([], 503),
        ]);

        $this->deleteJson("/api/documents/{$document->id}")->assertExactJson([
            'success' => true, 'message' => 'Dokumen berhasil dihapus.',
        ])->assertOk();
        $this->assertFileDoesNotExist($document->file_path);
        $this->assertDatabaseCount('documents', 0);
        $this->assertDatabaseCount('ekstraksi_halaman', 0);
        $this->assertDatabaseCount('ekstraksi_job', 0);
        Http::assertSentCount(2);
    }

    public function test_extraction_correction_and_embedding_keep_wire_contract(): void
    {
        $document = $this->document();
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/extraction" => Http::response(['status' => 'antre'], 202),
            self::AI."/api/docs/{$document->id}/pages/1" => Http::response(['saved' => true]),
            self::AI."/api/docs/{$document->id}/embed" => Http::response(['task_id' => 'test-task'], 202),
        ]);

        $this->postJson("/api/documents/{$document->id}/extraction", ['maks_halaman' => 2])
            ->assertStatus(202)->assertExactJson([
                'success' => true, 'message' => 'Ekstraksi dokumen diantrekan.', 'data' => ['status' => 'antre'],
            ]);
        $this->putJson("/api/documents/{$document->id}/pages/1", ['text' => 'Teks dikoreksi'])
            ->assertOk()->assertJsonPath('data.saved', true);
        $this->putJson("/api/documents/{$document->id}/pages/1", ['text' => 'Teks direvisi lagi'])->assertOk();
        $this->assertDatabaseCount('ekstraksi_halaman', 1);
        $this->assertDatabaseHas('ekstraksi_halaman', [
            'document_id' => $document->id, 'page_number' => 1, 'text' => 'Teks direvisi lagi', 'diperiksa' => 1,
        ]);
        $this->postJson("/api/documents/{$document->id}/embed", ['chunk_size' => 900])
            ->assertStatus(202)->assertJsonPath('data.task_id', 'test-task');
        Http::assertSent(fn (Request $request) => $request->data() === ['maks_halaman' => 2]);
        Http::assertSent(fn (Request $request) => $request->data() === ['chunk_size' => 900]);
        $this->assertDatabaseHas('document_logs', ['document_id' => $document->id, 'action' => 'completed']);
        $this->assertSame('processing', $document->fresh()->status);
    }

    public function test_failed_start_preserves_status_and_ai_error(): void
    {
        $document = $this->document();
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/extraction" => Http::response(['detail' => 'Dokumen belum siap'], 409),
        ]);

        $this->postJson("/api/documents/{$document->id}/extraction")->assertStatus(409)
            ->assertExactJson(['success' => false, 'message' => 'Dokumen belum siap']);
        $this->assertSame('pending', $document->fresh()->status);
        $this->assertDatabaseCount('document_logs', 0);
    }

    public function test_pause_sets_local_flag_when_ai_fails_and_is_idempotent(): void
    {
        $document = $this->document(['status' => 'processing']);
        $job = EkstraksiJob::create(['document_id' => $document->id, 'status' => 'berjalan']);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/extraction/pause" => Http::response([], 503),
        ]);

        $this->postJson("/api/documents/{$document->id}/extraction/pause")->assertStatus(202)
            ->assertJsonPath('data', ['document_id' => $document->id, 'jeda_diminta' => true]);
        $this->assertTrue($job->fresh()->jeda_diminta);
        $this->postJson("/api/documents/{$document->id}/extraction/pause")->assertOk()
            ->assertJsonPath('message', 'Permintaan jeda sudah diajukan sebelumnya.');
        $this->assertDatabaseHas('document_logs', ['document_id' => $document->id, 'action' => 'paused']);
        Http::assertSentCount(1);
    }

    public function test_failed_embedding_does_not_record_completion(): void
    {
        $document = $this->document(['status' => 'processing']);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/embed" => Http::response(['detail' => 'Koreksi belum selesai'], 409),
        ]);

        $this->postJson("/api/documents/{$document->id}/embed")->assertStatus(409)
            ->assertExactJson(['success' => false, 'message' => 'Koreksi belum selesai']);
        $this->assertDatabaseCount('document_logs', 0);
        $this->assertSame('processing', $document->fresh()->status);
    }

    public function test_status_prefers_live_ai_metadata(): void
    {
        $document = $this->document();
        $payload = ['document_id' => $document->id, 'status' => 'embedding', 'persen' => 35, 'task_id' => 'live-task'];
        $this->fakeAi([self::AI."/api/docs/{$document->id}/extraction" => Http::response($payload)]);

        $this->getJson("/api/documents/{$document->id}/extraction")->assertOk()
            ->assertExactJson(['success' => true, 'data' => $payload]);
    }

    public function test_status_fallback_ignores_placeholder_total_and_clamps_progress(): void
    {
        $document = $this->document(['total_pages' => 4, 'processed_pages' => 7]);
        EkstraksiJob::create([
            'document_id' => $document->id, 'status' => 'jeda', 'jeda_diminta' => true,
            'halaman_total' => 100, 'halaman_selesai' => 90, 'pesan' => 'Dijeda admin',
        ]);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/extraction" => Http::response([], 503)]);

        $this->getJson("/api/documents/{$document->id}/extraction")->assertOk()->assertExactJson([
            'success' => true,
            'data' => [
                'document_id' => $document->id, 'status' => 'jeda', 'jeda_diminta' => true,
                'halaman_total' => 4, 'halaman_selesai' => 4, 'persen' => 100, 'pesan' => 'Dijeda admin',
            ],
        ]);
    }

    public function test_empty_live_status_without_local_job_keeps_waiting_defaults(): void
    {
        $document = $this->document(['total_pages' => 2]);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/extraction" => Http::response([])]);

        $this->getJson("/api/documents/{$document->id}/extraction")->assertOk()->assertExactJson([
            'success' => true,
            'data' => [
                'document_id' => $document->id, 'status' => 'antre', 'jeda_diminta' => false,
                'halaman_total' => 2, 'halaman_selesai' => 0, 'persen' => 0, 'pesan' => null,
            ],
        ]);
    }

    public function test_page_list_falls_back_to_unchecked_local_pages(): void
    {
        $document = $this->document();
        $this->page($document, 2, true);
        $this->page($document, 1);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/pages*" => Http::response([], 503)]);

        $this->getJson("/api/documents/{$document->id}/pages?perlu_diperiksa=1")->assertOk()
            ->assertJsonPath('data.jumlah', 1)
            ->assertJsonPath('data.halaman.0', ['page_number' => 1, 'text' => 'Halaman 1', 'diperiksa' => false]);
    }

    public function test_rejected_correction_does_not_overwrite_local_page(): void
    {
        $document = $this->document();
        $this->page($document, 1);
        $this->fakeAi([
            self::AI."/api/docs/{$document->id}/pages/1" => Http::response(['detail' => 'Halaman dikunci'], 409),
        ]);

        $this->putJson("/api/documents/{$document->id}/pages/1", ['text' => 'Revisi ditolak'])
            ->assertStatus(409)->assertExactJson(['success' => false, 'message' => 'Halaman dikunci']);
        $this->assertDatabaseHas('ekstraksi_halaman', [
            'document_id' => $document->id, 'page_number' => 1, 'text' => 'Halaman 1', 'diperiksa' => 0,
        ]);
    }

    public function test_successful_empty_page_list_is_not_replaced_with_local_pages(): void
    {
        $document = $this->document();
        $this->page($document, 1);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/pages*" => Http::response([])]);

        $this->getJson("/api/documents/{$document->id}/pages")->assertOk()
            ->assertExactJson(['success' => true, 'data' => []]);
    }

    public function test_missing_document_returns_404_before_validation_or_ai_calls(): void
    {
        $this->fakeAi();

        $this->postJson('/api/documents/99999/replace')->assertNotFound();
        $this->putJson('/api/documents/99999/pages/1', ['text' => ''])->assertNotFound();
        $this->getJson('/api/documents/99999')->assertNotFound();
        Http::assertNothingSent();
    }

    public function test_chunk_endpoint_returns_empty_array_when_ai_is_unavailable_without_mutating_document(): void
    {
        $document = $this->document(['status' => 'completed', 'total_chunks' => 12]);
        $this->fakeAi([self::AI."/api/docs/{$document->id}/chunks" => Http::response(['detail' => 'Synthetic outage'], 503)]);

        $this->getJson("/api/documents/{$document->id}/chunks")->assertOk()->assertExactJson([]);

        $this->assertSame('completed', $document->fresh()->status);
        $this->assertSame(12, $document->total_chunks);
        Http::assertSentCount(1);
    }

    public function test_chunk_endpoint_preserves_successful_ai_payload_without_envelope(): void
    {
        $document = $this->document();
        $chunks = ['document_id' => $document->id, 'chunks' => [['id' => 'child-1', 'text' => 'Teks dokumen']]];
        $this->fakeAi([self::AI."/api/docs/{$document->id}/chunks" => Http::response($chunks)]);

        $this->getJson("/api/documents/{$document->id}/chunks")->assertOk()->assertExactJson($chunks);
        Http::assertSentCount(1);
    }

    private function document(array $attributes = []): Document
    {
        Storage::disk('local')->put('documents/source.txt', 'Isi dokumen awal');

        return Document::create(array_merge([
            'title' => 'SOP Pengujian', 'original_name' => 'source.txt',
            'file_path' => Storage::disk('local')->path('documents/source.txt'),
            'status' => 'pending', 'pdf_type' => 'unknown', 'uploaded_by' => $this->admin->id,
        ], $attributes));
    }

    private function page(Document $document, int $number, bool $checked = false): void
    {
        EkstraksiHalaman::create([
            'document_id' => $document->id, 'page_number' => $number,
            'text' => "Halaman {$number}", 'diperiksa' => $checked,
        ]);
    }

    private function fakeAi(array $responses = []): void
    {
        Http::fake(array_merge([
            self::AI.'/health' => Http::response(['status' => 'healthy']),
            self::AI.'/api/docs/vector-counts' => Http::response(['counts' => []]),
        ], $responses));
    }
}
