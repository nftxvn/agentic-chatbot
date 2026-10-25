<?php

namespace Tests\Feature;

use App\Models\ApiKey;
use App\Models\ChatLog;
use App\Services\Channels\AiChatGateway;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class PublicChatGatewayContractTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config(['services.ai.url' => 'http://ai.example.test', 'services.ai_microservice.token' => 'internal-token']);
        ApiKey::create(['name' => 'Test client', 'key' => 'synthetic-api-key', 'is_active' => true]);
        $this->withHeader('Authorization', 'Bearer synthetic-api-key');
        Http::preventStrayRequests();
    }

    public function test_public_json_preserves_payload_sources_and_private_telemetry(): void
    {
        Http::fake(['http://ai.example.test/api/chat/message' => Http::response([
            'reply' => 'Jawaban', 'sources' => [['document_id' => 1, 'page' => 2]],
        ])]);
        $this->postJson('/api/v1/chat', ['query' => 'Pertanyaan', 'session_id' => 'public-session', 'document_ids' => [1]])
            ->assertOk()->assertJsonPath('answer', 'Jawaban')->assertJsonPath('sources.0.page', 2)
            ->assertJsonPath('is_fallback', false)->assertJsonPath('is_human_takeover', false);
        Http::assertSent(fn ($r) => $r['message'] === 'Pertanyaan' && $r['phone_number'] === 'public-session'
            && $r['document_ids'] === [1] && $r->hasHeader('Authorization', 'Bearer internal-token'));
        $this->assertNull(ChatLog::sole()->query);
        $this->assertNull(ChatLog::sole()->answer);
    }

    public function test_public_json_ai_error_uses_existing_local_degradation_response(): void
    {
        Http::fake(['http://ai.example.test/api/chat/message' => Http::response([], 503)]);
        $this->postJson('/api/v1/chat', ['query' => 'Unknown information', 'session_id' => 'public-session'])
            ->assertOk()->assertJsonPath('is_fallback', true)->assertJsonPath('degraded_mode', true);
    }

    private function fakeStream(string $bytes, string $error = ''): void
    {
        $gateway = \Mockery::mock(AiChatGateway::class);
        $gateway->shouldReceive('stream')->once()->withArgs(function ($url, $token, $payload, $consume) use ($bytes) {
            $this->assertSame('http://ai.example.test/api/chat/stream', $url);
            $this->assertSame('internal-token', $token);
            $this->assertFalse($payload['include_debug']);
            $this->assertSame('public-session', $payload['session_id']);
            $this->assertSame(strlen($bytes), $consume(null, $bytes));
            return true;
        })->andReturn($error);
        $this->app->instance(AiChatGateway::class, $gateway);
    }

    public function test_public_stream_preserves_raw_bytes_and_headers(): void
    {
        $bytes = "data: {\"type\":\"chunk\",\"content\":\"Jawaban\"}\n\ndata: {\"type\":\"done\",\"content\":\"\"}\n\n";
        $this->fakeStream($bytes);
        $response = $this->postJson('/api/v1/chat/stream', ['query' => 'Pertanyaan', 'session_id' => 'public-session']);
        $response->assertOk()->assertHeader('Content-Type', 'text/event-stream; charset=utf-8')->assertHeader('X-Accel-Buffering', 'no');
        $this->assertSame($bytes, $response->streamedContent());
        Http::assertNothingSent();
    }

    public function test_empty_stream_returns_local_chunk_and_done_events(): void
    {
        $this->fakeStream('', 'connection failed');
        $response = $this->postJson('/api/v1/chat/stream', ['query' => 'Unknown information', 'session_id' => 'public-session']);
        $content = $response->streamedContent();
        $this->assertStringContainsString('"type":"chunk"', $content);
        $this->assertStringContainsString('"type":"done"', $content);
    }
}
