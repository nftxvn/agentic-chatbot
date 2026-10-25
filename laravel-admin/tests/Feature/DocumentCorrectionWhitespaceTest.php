<?php

namespace Tests\Feature;

use App\Models\Document;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class DocumentCorrectionWhitespaceTest extends TestCase
{
    use RefreshDatabase;

    private const AI = 'http://ai.example.test';

    private Document $document;

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'services.ai_microservice.url' => self::AI,
            'services.ai_microservice.token' => 'correction-whitespace-test-token',
        ]);
        Storage::fake('local');
        Http::preventStrayRequests();
        $admin = User::factory()->create();
        $this->actingAs($admin);
        Storage::disk('local')->put('documents/source.txt', 'Synthetic source');
        $this->document = Document::create([
            'title' => 'Synthetic document',
            'original_name' => 'source.txt',
            'file_path' => Storage::disk('local')->path('documents/source.txt'),
            'status' => 'menunggu_koreksi',
            'pdf_type' => 'text',
            'uploaded_by' => $admin->id,
        ]);
    }

    #[DataProvider('formattedCorrectionCases')]
    public function test_editor_formatting_reaches_python_and_local_page_unchanged(string $text): void
    {
        $endpoint = self::AI."/api/docs/{$this->document->id}/pages/1";
        Http::fake([$endpoint => Http::response([
            'document_id' => $this->document->id,
            'page_number' => 1,
            'tersimpan' => true,
        ])]);

        $this->putJson("/api/documents/{$this->document->id}/pages/1", ['text' => $text])
            ->assertOk()->assertJsonPath('success', true);

        Http::assertSent(fn (Request $request) => $request->url() === $endpoint
            && $request->method() === 'PUT'
            && $request->data() === ['text' => $text]);
        $this->assertDatabaseHas('ekstraksi_halaman', [
            'document_id' => $this->document->id,
            'page_number' => 1,
            'text' => $text,
            'diperiksa' => 1,
        ]);
    }

    public static function formattedCorrectionCases(): array
    {
        return [
            'leading indentation' => ["    1. Langkah pertama\n    2. Langkah kedua"],
            'trailing newline' => ["# Panduan layanan arsip\n\nWaktu penyelesaian 37 menit.\n"],
            'tabs and CRLF' => ["\tTabel hasil koreksi\r\n\tKolom A\tKolom B\r\n\r\n"],
            'nonbreaking spaces around content' => ["\u{00A0}Hasil koreksi\u{00A0}"],
            'zero width spaces around content' => ["\u{200B}Hasil koreksi\u{200B}"],
        ];
    }

    #[DataProvider('emptyCorrectionCases')]
    public function test_empty_correction_is_rejected_before_python_or_local_write(string $text): void
    {
        $this->putJson("/api/documents/{$this->document->id}/pages/1", ['text' => $text])
            ->assertUnprocessable()->assertJsonValidationErrors('text');

        Http::assertNothingSent();
        $this->assertDatabaseMissing('ekstraksi_halaman', [
            'document_id' => $this->document->id,
            'page_number' => 1,
        ]);
    }

    public static function emptyCorrectionCases(): array
    {
        return [
            'empty string' => [''],
            'spaces only' => ['   '],
            'tabs and newlines only' => ["\t\r\n\n"],
            'nonbreaking spaces only' => ["\u{00A0}\u{00A0}"],
            'zero width spaces only' => ["\u{200B}\u{200B}"],
        ];
    }

    public function test_other_admin_routes_still_trim_strings(): void
    {
        $this->postJson('/api/categories', [
            'name' => '  Synthetic category  ',
            'vision_prompt' => "\n  Instruksi kategori  \n",
            'ui_layout' => '  general  ',
        ])->assertOk()->assertJsonPath('data.name', 'Synthetic category')
            ->assertJsonPath('data.vision_prompt', 'Instruksi kategori')
            ->assertJsonPath('data.ui_layout', 'general');

        Http::assertNothingSent();
    }
}
