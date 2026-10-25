<?php

namespace Tests\Feature;

use App\Services\AiMicroserviceClient;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class AiMicroserviceClientContractTest extends TestCase
{
    private const BASE_URL = 'http://ai.example.test';

    protected function setUp(): void
    {
        parent::setUp();
        config([
            'services.ai_microservice.url' => self::BASE_URL.'///',
            'services.ai_microservice.token' => 'synthetic-internal-token',
        ]);
        Http::preventStrayRequests();
    }

    public static function envelopeOperations(): array
    {
        return [
            'cancel' => ['cancelDocument', [42], 'POST', '/api/docs/42/cancel', 10, 5, 'Gagal membatalkan di AI service', false],
            'start' => ['mulaiEkstraksi', [42], 'POST', '/api/docs/42/extraction', 30, 10, 'Gagal memulai ekstraksi', true],
            'pause' => ['jedaEkstraksi', [42], 'POST', '/api/docs/42/extraction/pause', 15, 5, 'Gagal meminta jeda', true],
            'status' => ['statusEkstraksi', [42], 'GET', '/api/docs/42/extraction', 15, 10, 'Gagal membaca status ekstraksi', true],
            'pages' => ['daftarHalaman', [42], 'GET', '/api/docs/42/pages?perlu_diperiksa=0', 30, 10, 'Gagal memuat teks halaman', true],
            'correction' => ['simpanKoreksiHalaman', [42, 3, 'Teks koreksi'], 'PUT', '/api/docs/42/pages/3', 30, 10, 'Gagal menyimpan koreksi halaman', true],
            'dimensions' => ['ukuranHalaman', [42], 'GET', '/api/docs/42/pages/dimensions', 15, 10, 'Gagal mengambil ukuran halaman', true],
            'preview' => ['pratinjauPotongan', [42], 'GET', '/api/docs/42/chunks/preview', 30, 10, 'Gagal membuat pratinjau potongan', true],
            'embed' => ['simpanKeKorpus', [42], 'POST', '/api/docs/42/embed', 30, 10, 'Gagal menyimpan ke korpus', true],
            'delete' => ['deleteDocument', [42], 'DELETE', '/api/docs/42', 15, 10, 'Gagal menghapus vektor dokumen', true],
        ];
    }

    #[DataProvider('envelopeOperations')]
    public function test_operations_preserve_auth_url_timeouts_and_success_envelope(
        string $operation, array $arguments, string $method, string $path,
        int $timeout, int $connectTimeout, string $fallback, bool $hasErrorStatus,
    ): void {
        $payload = ['status' => 'menunggu_koreksi', 'halaman_selesai' => 3];
        Http::fake(function (Request $request, array $options) use ($method, $path, $timeout, $connectTimeout, $payload) {
            $this->assertSame($method, $request->method());
            $this->assertSame(self::BASE_URL.$path, $request->url());
            $this->assertTrue($request->hasHeader('Authorization', 'Bearer synthetic-internal-token'));
            $this->assertSame($timeout, $options['timeout']);
            $this->assertSame($connectTimeout, $options['connect_timeout']);

            return Http::response($payload, 202);
        });

        $this->assertSame(['success' => true, 'data' => $payload], (new AiMicroserviceClient)->$operation(...$arguments));
        Http::assertSentCount(1);
    }

    #[DataProvider('envelopeOperations')]
    public function test_http_failure_keeps_endpoint_specific_message_and_status_policy(
        string $operation, array $arguments, string $method, string $path,
        int $timeout, int $connectTimeout, string $fallback, bool $hasErrorStatus,
    ): void {
        Http::fake(['*' => Http::response(['detail' => null], 409)]);
        $expected = ['success' => false, 'message' => $fallback.' (HTTP 409)'];
        if ($hasErrorStatus) {
            $expected['status'] = 409;
        }

        $this->assertSame($expected, (new AiMicroserviceClient)->$operation(...$arguments));
        Http::assertSentCount(1);
    }

    public function test_start_filters_category_options_and_preserves_explicit_zero_page_limit(): void
    {
        Http::fake(['*' => Http::response(['status' => 'pending'])]);
        (new AiMicroserviceClient)->mulaiEkstraksi(42, 0, [
            'category_prompt' => 'Baca formulir persis', 'job_titles' => ['Kepala Bidang'],
            'vision_model' => '', 'custom_prompts' => ['dasar' => 'Petunjuk khusus'],
            'unknown' => 'tidak dikirim',
        ]);

        Http::assertSent(fn (Request $request) => $request->data() === [
            'maks_halaman' => 0, 'category_prompt' => 'Baca formulir persis',
            'job_titles' => ['Kepala Bidang'], 'custom_prompts' => ['dasar' => 'Petunjuk khusus'],
        ]);
    }

    public static function emptyObjectOperations(): array
    {
        return ['start' => ['mulaiEkstraksi'], 'embed' => ['simpanKeKorpus']];
    }

    #[DataProvider('emptyObjectOperations')]
    public function test_empty_start_and_embed_payloads_remain_json_objects(string $operation): void
    {
        Http::fake(['*' => Http::response([])]);
        (new AiMicroserviceClient)->$operation(42);

        Http::assertSent(fn (Request $request) => $request->body() === '{}'
            && $request->hasHeader('Content-Type', 'application/json'));
    }

    public function test_empty_category_options_still_warn_without_filling_the_payload(): void
    {
        Log::spy();
        Http::fake(['*' => Http::response([])]);
        (new AiMicroserviceClient)->mulaiEkstraksi(42, null, ['category_prompt' => '', 'job_titles' => []]);

        Http::assertSent(fn (Request $request) => $request->body() === '{}');
        Log::shouldHaveReceived('warning')->once()->withArgs(fn ($message, $context) =>
            $message === 'Setelan kategori tidak sampai ke layanan AI — seluruh nilainya kosong.'
            && $context['document_id'] === 42
            && $context['kunci_dikirim'] === ['category_prompt', 'job_titles']);
    }

    public function test_editor_payloads_keep_filter_text_zoom_and_preview_options(): void
    {
        Http::fake(['*' => Http::response(['ok' => true])]);
        $client = new AiMicroserviceClient;
        $client->daftarHalaman(42, true);
        $client->simpanKoreksiHalaman(42, 3, "Baris pertama\nBaris kedua: é");
        $client->citraHalaman(42, 3, 1.5);
        $options = ['chunk_size' => 0, 'overlap' => 20, 'headings' => ['Judul']];
        $client->pratinjauPotongan(42, $options);
        $client->simpanKeKorpus(42, $options);

        Http::assertSent(fn (Request $request) => $request->url() === self::BASE_URL.'/api/docs/42/pages?perlu_diperiksa=1');
        Http::assertSent(fn (Request $request) => $request->method() === 'PUT'
            && $request->data() === ['text' => "Baris pertama\nBaris kedua: é"]);
        Http::assertSent(fn (Request $request) => $request->url() === self::BASE_URL.'/api/docs/42/pages/3/image?zoom=1.5');
        foreach (['chunks/preview', 'embed'] as $endpoint) {
            Http::assertSent(fn (Request $request) => $request->method() === 'POST'
                && $request->url() === self::BASE_URL.'/api/docs/42/'.$endpoint && $request->data() === $options);
        }
        Http::assertSentCount(5);
    }

    public static function validationDetails(): array
    {
        return [
            'string' => ['  Antrean belum siap  ', '  Antrean belum siap  '],
            'validation list' => [[['loc' => ['body', 'maks_halaman'], 'msg' => 'Harus positif'], 'Model tidak tersedia'], 'body.maks_halaman: Harus positif, Model tidak tersedia'],
            'unknown array' => [[['kode' => 'é']], '[{"kode":"é"}]'],
            'empty array' => [[], '[]'],
            'blank string' => ['  ', 'Gagal memulai ekstraksi (HTTP 422)'],
            'boolean' => [false, 'Gagal memulai ekstraksi (HTTP 422)'],
        ];
    }

    #[DataProvider('validationDetails')]
    public function test_fastapi_error_details_keep_format_and_unicode(mixed $detail, string $message): void
    {
        Http::fake(['*' => Http::response(['detail' => $detail], 422)]);

        $this->assertSame(['success' => false, 'message' => $message, 'status' => 422],
            (new AiMicroserviceClient)->mulaiEkstraksi(42));
    }

    public function test_connection_failures_keep_per_operation_fallback_without_retry(): void
    {
        Log::spy();
        $attempts = 0;
        Http::fake(function () use (&$attempts) {
            $attempts++;
            return Http::failedConnection('synthetic outage');
        });
        $client = new AiMicroserviceClient;

        $this->assertFalse($client->healthCheck());
        $this->assertSame(['success' => false, 'message' => 'Tidak dapat terhubung ke AI service: synthetic outage'], $client->cancelDocument(42));
        $this->assertSame(['success' => false, 'message' => 'synthetic outage'], $client->mulaiEkstraksi(42));
        $this->assertNull($client->citraHalaman(42, 1));
        $this->assertSame([], $client->getDocumentChunks(42));
        $this->assertSame([], $client->getVectorCounts());
        $this->assertSame(6, $attempts);
    }

    public function test_image_response_preserves_binary_body_and_failure_returns_null(): void
    {
        $jpeg = "\xFF\xD8\xFF\x00synthetic-jpeg\xFF\xD9";
        Http::fakeSequence()->push($jpeg, 200, ['Content-Type' => 'image/jpeg'])->push([], 404);
        $client = new AiMicroserviceClient;

        $response = $client->citraHalaman(42, 3);
        $this->assertSame($jpeg, $response->body());
        $this->assertSame('image/jpeg', $response->header('Content-Type'));
        $this->assertNull($client->citraHalaman(42, 99));
        Http::assertSent(fn (Request $request) => $request->url() === self::BASE_URL.'/api/docs/42/pages/3/image?zoom=2');
    }

    public function test_health_chunks_and_counts_keep_unwrapped_results_and_config_snapshot(): void
    {
        Http::fake([
            self::BASE_URL.'/health' => Http::response(['status' => 'degraded'], 503),
            self::BASE_URL.'/api/docs/42/chunks' => Http::response(['parents' => [], 'children' => [['id' => 'child-1']]]),
            self::BASE_URL.'/api/docs/vector-counts' => Http::sequence()->push(['counts' => ['42' => 7]])->push([])->push([], 503),
        ]);
        $client = new AiMicroserviceClient;
        config(['services.ai_microservice.url' => 'http://changed.example.test', 'services.ai_microservice.token' => 'changed-token']);

        $this->assertFalse($client->healthCheck());
        $this->assertSame(['parents' => [], 'children' => [['id' => 'child-1']]], $client->getDocumentChunks(42));
        $this->assertSame(['42' => 7], $client->getVectorCounts());
        $this->assertSame([], $client->getVectorCounts());
        $this->assertSame([], $client->getVectorCounts());
        Http::assertSent(fn (Request $request) => $request->hasHeader('Authorization', 'Bearer synthetic-internal-token'));
        Http::assertSentCount(5);
    }

    public static function chunkFailureStatuses(): array
    {
        return ['not found' => [404], 'rate limited' => [429], 'unavailable' => [503]];
    }

    #[DataProvider('chunkFailureStatuses')]
    public function test_chunk_http_failure_returns_empty_array_without_retry(int $status): void
    {
        Http::fake(['*' => Http::response(['detail' => 'Synthetic upstream failure'], $status)]);

        $this->assertSame([], (new AiMicroserviceClient)->getDocumentChunks(42));
        Http::assertSentCount(1);
    }

    public function test_protected_error_formatter_override_is_used_by_both_operation_groups(): void
    {
        Http::fake(['*' => Http::response([], 422)]);
        $client = new class extends AiMicroserviceClient {
            protected function extractErrorMessage($response, string $fallback = 'Terjadi kesalahan pada AI service'): string
            {
                return 'Pesan kustom';
            }
        };

        $this->assertSame('Pesan kustom', $client->cancelDocument(42)['message']);
        $this->assertSame('Pesan kustom', $client->mulaiEkstraksi(42)['message']);
    }
}
