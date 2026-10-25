<?php

namespace Tests\Feature;

use App\Models\Document;
use App\Models\EkstraksiJob;
use App\Models\User;
use App\Services\Documents\DocumentWorkflowService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class DocumentCancellationFenceTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.ai_microservice.url' => 'http://ai.example.test']);
        Storage::fake('local');
        Http::preventStrayRequests();
        $this->actingAs(User::factory()->create());
    }

    private function document(): Document
    {
        Storage::disk('local')->put('documents/source.txt', 'Synthetic source');
        $document = Document::create([
            'title' => 'Synthetic cancellation', 'original_name' => 'source.txt',
            'file_path' => Storage::disk('local')->path('documents/source.txt'),
            'status' => 'processing', 'uploaded_by' => auth()->id(),
        ]);
        DB::table('documents')->where('id', $document->id)->update(['processing_token' => 'old-generation']);
        EkstraksiJob::create(['document_id' => $document->id, 'status' => 'berjalan']);

        return $document;
    }

    private function failedAiWithFenceAssertion(Document $document): void
    {
        Http::fake(function (Request $request) use ($document) {
            if (str_ends_with($request->url(), '/cancel')) {
                $this->assertDatabaseHas('documents', [
                    'id' => $document->id, 'cancellation_requested' => 1,
                    'processing_token' => 'old-generation',
                ]);
                $this->assertDatabaseHas('ekstraksi_job', [
                    'document_id' => $document->id, 'status' => 'gagal',
                ]);
            }

            return Http::response(['detail' => 'Synthetic service unavailable'], 503);
        });
    }

    public function test_cancel_persists_fence_before_calling_an_unavailable_python_service(): void
    {
        $document = $this->document();
        $other = $this->document();
        $this->failedAiWithFenceAssertion($document);

        $this->postJson("/api/documents/{$document->id}/cancel")->assertOk()
            ->assertJsonPath('data.document.status', 'failed');

        $this->assertDatabaseHas('documents', ['id' => $document->id, 'cancellation_requested' => 1]);
        $this->assertDatabaseHas('document_vector_cleanups', [
            'document_id' => $document->id, 'operation_token' => 'old-generation',
        ]);
        $this->assertDatabaseHas('documents', ['id' => $other->id, 'cancellation_requested' => 0]);
        $this->assertDatabaseHas('document_logs', ['document_id' => $document->id, 'action' => 'cancelled']);
        Http::assertSentCount(1);
    }

    public function test_replacement_fences_the_old_worker_before_resetting_pages_even_if_python_is_down(): void
    {
        $document = $this->document();
        $this->failedAiWithFenceAssertion($document);

        $this->post("/api/documents/{$document->id}/replace", [
            'pdf_file' => UploadedFile::fake()->createWithContent('replacement.txt', 'New synthetic source'),
        ])->assertOk();

        $this->assertDatabaseHas('documents', ['id' => $document->id, 'cancellation_requested' => 1]);
        $this->assertSame('New synthetic source', file_get_contents($document->fresh()->file_path));
        $this->assertDatabaseHas('document_vector_cleanups', [
            'document_id' => $document->id, 'operation_token' => '',
        ]);
    }

    public function test_delete_fences_the_worker_before_requesting_remote_cleanup(): void
    {
        $document = $this->document();
        $this->failedAiWithFenceAssertion($document);

        $this->deleteJson("/api/documents/{$document->id}")->assertOk();

        $this->assertDatabaseMissing('documents', ['id' => $document->id]);
        $this->assertDatabaseHas('document_vector_cleanups', [
            'document_id' => $document->id, 'operation_token' => '',
        ]);
        Http::assertSentCount(2);
    }

    public function test_cancel_reloads_state_if_a_resume_changed_a_previously_loaded_model(): void
    {
        $document = $this->document();
        Http::fake(['*' => Http::response([], 503)]);
        $workflow = app(DocumentWorkflowService::class);
        $workflow->cancel($document, null);
        $document->refresh();

        DB::table('documents')->where('id', $document->id)->update([
            'processing_token' => 'new-generation', 'cancellation_requested' => false,
            'status' => 'processing',
        ]);
        $workflow->cancel($document, null);

        $this->assertDatabaseHas('documents', [
            'id' => $document->id, 'processing_token' => 'new-generation',
            'cancellation_requested' => 1,
        ]);
        $this->assertDatabaseHas('document_vector_cleanups', [
            'document_id' => $document->id, 'operation_token' => 'old-generation',
        ]);
        $this->assertDatabaseHas('document_vector_cleanups', [
            'document_id' => $document->id, 'operation_token' => 'new-generation',
        ]);
    }

    public function test_repeated_cancel_keeps_one_cleanup_per_generation(): void
    {
        $document = $this->document();
        Http::fake(['*' => Http::response([], 503)]);
        $workflow = app(DocumentWorkflowService::class);
        $workflow->cancel($document, null);
        $workflow->cancel($document, null);

        $this->assertSame(1, DB::table('document_vector_cleanups')->where('document_id', $document->id)->count());
    }

    public function test_cleanup_deadline_is_utc_even_with_jakarta_application_timezone(): void
    {
        $this->travelTo(\Illuminate\Support\Carbon::parse('2026-10-25 21:00:00', 'Asia/Jakarta'));
        $document = $this->document();
        Http::fake(['*' => Http::response([], 503)]);

        app(DocumentWorkflowService::class)->cancel($document, null);

        $this->assertSame('2026-10-25 14:00:00', DB::table('document_vector_cleanups')->value('available_at'));
    }

    public function test_cancel_of_completed_corpus_does_not_enqueue_vector_deletion(): void
    {
        $document = $this->document();
        $document->forceFill(['status' => 'completed', 'processed_at' => now()])->save();
        Http::fake(['*' => Http::response([], 503)]);

        $this->postJson("/api/documents/{$document->id}/cancel")->assertOk();

        $this->assertDatabaseCount('document_vector_cleanups', 0);
    }

    public function test_outbox_insert_failure_rolls_back_fence_before_any_http_request(): void
    {
        $document = $this->document();
        DB::statement("CREATE TRIGGER synthetic_cleanup_failure BEFORE INSERT ON document_vector_cleanups BEGIN SELECT RAISE(ABORT, 'synthetic outbox failure'); END");
        Http::fake(['*' => Http::response([], 503)]);

        $this->postJson("/api/documents/{$document->id}/cancel")->assertStatus(500);

        $this->assertDatabaseHas('documents', [
            'id' => $document->id, 'cancellation_requested' => 0, 'status' => 'processing',
        ]);
        $this->assertDatabaseHas('ekstraksi_job', ['document_id' => $document->id, 'status' => 'berjalan']);
        Http::assertNothingSent();
    }
}
