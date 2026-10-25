<?php

namespace Tests\Feature;

use App\Models\ChatLog;
use App\Services\Channels\AiChatGateway;
use App\Services\Channels\TelegramAiResponder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class TelegramStreamContractTest extends TestCase
{
    use RefreshDatabase;

    private function responder(array $chunks, string $error = '', array $times = []): TelegramAiResponder
    {
        $gateway = \Mockery::mock(AiChatGateway::class);
        $gateway->shouldReceive('stream')->once()->withArgs(function ($url, $token, $payload, $consume) use ($chunks) {
            $this->assertSame('http://ai.example.test/api/chat/stream', $url);
            $this->assertSame('internal-token', $token);
            $this->assertSame('telegram-123', $payload['session_id']);
            foreach ($chunks as $chunk) {
                $this->assertSame(strlen($chunk), $consume(null, $chunk));
            }
            return true;
        })->andReturn($error);
        if ($times) {
            $responder = \Mockery::mock(TelegramAiResponder::class, [$gateway])->makePartial()->shouldAllowMockingProtectedMethods();
            $responder->shouldReceive('timestamp')->andReturn(...$times);
            return $responder;
        }
        return new TelegramAiResponder($gateway);
    }

    private function fakeTelegram(array $editResponses = []): void
    {
        Http::preventStrayRequests();
        $edit = Http::sequence();
        foreach ($editResponses as $status) {
            $edit->push(['ok' => $status === 200], $status);
        }
        $edit->whenEmpty(Http::response(['ok' => true]));
        Http::fake([
            '*sendChatAction' => Http::response(['ok' => true]),
            '*sendMessage' => Http::response(['ok' => true, 'result' => ['message_id' => 7]]),
            '*editMessageText' => $edit,
        ]);
    }

    public function test_webhook_reassembles_fragmented_sse_and_ignores_debug_malformed_and_unterminated_data(): void
    {
        $this->fakeTelegram();
        $responder = $this->responder([
            'data: {"type":"chu',
            "nk\",\"content\":\"Halo \"}\r\n\r\n",
            "data: invalid\ndata: {\"type\":\"debug\",\"content\":\"secret\"}\n",
            "data: {\"type\":\"chunk\",\"content\":\"warga\"}\n\n",
            'data: {"type":"chunk","content":"unfinished"}',
        ]);
        $responder->replyToWebhook('token', 123, 'Pertanyaan', 'http://ai.example.test/', 'internal-token', 'Naufal', 'naufal');
        Http::assertSent(fn ($r) => str_contains($r->url(), 'editMessageText') && $r['text'] === 'Halo warga' && $r['parse_mode'] === 'Markdown');
        $log = ChatLog::sole();
        $this->assertSame('Pengguna Telegram', $log->sender_identifier);
        $this->assertNull($log->query);
        $this->assertNull($log->answer);
        $this->assertNull($log->sources_json);
    }

    public function test_webhook_markdown_failure_edits_plain_text_without_sending_new_message(): void
    {
        $this->fakeTelegram([400, 200]);
        $this->responder(["data: {\"type\":\"chunk\",\"content\":\"Jawaban\"}\n"])
            ->replyToWebhook('token', 123, 'Pertanyaan', 'http://ai.example.test', 'internal-token');
        Http::assertSent(fn ($r) => str_contains($r->url(), 'editMessageText') && !isset($r['parse_mode']) && $r['text'] === 'Jawaban');
        $this->assertCount(1, Http::recorded(fn ($r) => str_contains($r->url(), 'sendMessage')));
    }

    public function test_polling_failed_edits_send_new_message_as_existing_fallback(): void
    {
        $this->fakeTelegram([400, 400]);
        $this->responder(["data: {\"type\":\"chunk\",\"content\":\"Jawaban\"}\n"])
            ->replyToPolling('token', 123, 'Pertanyaan', 'Naufal', null, 'http://ai.example.test', 'internal-token');
        $this->assertCount(2, Http::recorded(fn ($r) => str_contains($r->url(), 'sendMessage')));
        Http::assertSent(fn ($r) => str_contains($r->url(), 'sendMessage') && $r['text'] === 'Jawaban');
    }

    public function test_webhook_failed_edits_keep_existing_no_new_message_behavior(): void
    {
        $this->fakeTelegram([400, 400]);
        $this->responder(["data: {\"type\":\"chunk\",\"content\":\"Jawaban\"}\n"])
            ->replyToWebhook('token', 123, 'Pertanyaan', 'http://ai.example.test', 'internal-token');
        $this->assertCount(1, Http::recorded(fn ($r) => str_contains($r->url(), 'sendMessage')));
    }

    public function test_webhook_draft_uses_existing_twelve_tenths_and_twenty_character_threshold(): void
    {
        $this->fakeTelegram();
        $text = str_repeat('a', 20);
        $this->responder(['data: ' . json_encode(['type' => 'chunk', 'content' => $text]) . "\n"], '', [0.0, 0.0, 1.3, 2.0])
            ->replyToWebhook('token', 123, 'Pertanyaan', 'http://ai.example.test', 'internal-token');
        Http::assertSent(fn ($r) => str_contains($r->url(), 'editMessageText') && $r['text'] === $text . "\n\n▌");
    }

    public function test_polling_does_not_use_webhook_draft_threshold(): void
    {
        $this->fakeTelegram();
        $text = str_repeat('a', 20);
        $this->responder(['data: ' . json_encode(['type' => 'chunk', 'content' => $text]) . "\n"], '', [0.0, 0.0, 1.3, 2.0])
            ->replyToPolling('token', 123, 'Pertanyaan', 'Naufal', null, 'http://ai.example.test', 'internal-token');
        $this->assertCount(1, Http::recorded(fn ($r) => str_contains($r->url(), 'editMessageText')));
    }

    public function test_polling_draft_uses_fifteen_tenths_and_twenty_five_character_threshold(): void
    {
        $this->fakeTelegram();
        $text = str_repeat('a', 25);
        $this->responder(['data: ' . json_encode(['type' => 'chunk', 'content' => $text]) . "\n"], '', [0.0, 0.0, 1.6, 2.0])
            ->replyToPolling('token', 123, 'Pertanyaan', 'Naufal', null, 'http://ai.example.test', 'internal-token');
        Http::assertSent(fn ($r) => str_contains($r->url(), 'editMessageText') && $r['text'] === $text . "\n\n▌");
    }
}
