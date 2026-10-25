<?php

namespace Tests\Feature;

use App\Models\AppSetting;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class SettingsContractTest extends TestCase
{
    use RefreshDatabase;

    private const PROMPT_HASH = 'cafb8068c7aed0c1231d83c84d50799423d4b4d7a225c4737d60cfc6223fdd23';

    protected function setUp(): void
    {
        parent::setUp();
        $this->actingAs(User::factory()->create());
        Http::preventStrayRequests();
    }

    public function test_chatbot_defaults_keep_types_prompt_and_dashboard_fields(): void
    {
        $response = $this->getJson('/api/settings/chatbot')->assertOk()
            ->assertJsonStructure([
                'llm_model_name', 'chatbot_name', 'chatbot_persona', 'rag_system_prompt',
                'rag_temperature', 'rag_top_k', 'rag_num_ctx', 'chatbot_greeting',
                'chatbot_fallback_message', 'rag_citation_enabled', 'default_rag_prompt',
            ])->assertJsonPath('llm_model_name', 'qwen2.5:7b')
            ->assertJsonPath('rag_temperature', 0.2)->assertJsonPath('rag_top_k', 8)
            ->assertJsonPath('rag_num_ctx', 6144)->assertJsonPath('rag_citation_enabled', true);

        $this->assertSame(self::PROMPT_HASH, hash('sha256', $response->json('default_rag_prompt')));
        $this->assertSame($response->json('default_rag_prompt'), $response->json('rag_system_prompt'));
        $this->assertSame(0, AppSetting::count());
    }

    public function test_chatbot_update_preserves_omitted_model_context_and_numeric_casts(): void
    {
        AppSetting::setVal('llm_model_name', 'existing-model');
        AppSetting::setVal('rag_num_ctx', '8192');

        $this->postJson('/api/settings/chatbot', $this->chatbotPayload())
            ->assertOk()->assertJsonPath('settings.llm_model_name', 'existing-model')
            ->assertJsonPath('settings.rag_num_ctx', 8192)->assertJsonPath('settings.rag_top_k', 5)
            ->assertJsonPath('settings.rag_temperature', 0.4)
            ->assertJsonPath('settings.rag_citation_enabled', false)
            ->assertJsonPath('settings.chatbot_greeting', '');
        $this->assertSame('false', AppSetting::getVal('rag_citation_enabled'));
        $this->assertSame('5', AppSetting::getVal('rag_top_k'));
        Http::assertNothingSent();
    }

    public function test_invalid_chatbot_values_do_not_change_settings(): void
    {
        $this->postJson('/api/settings/chatbot', array_merge($this->chatbotPayload(), [
            'rag_temperature' => 2, 'rag_top_k' => 0, 'rag_num_ctx' => 100,
        ]))->assertUnprocessable()->assertJsonValidationErrors(['rag_temperature', 'rag_top_k', 'rag_num_ctx']);
        $this->assertSame(0, AppSetting::count());
    }

    public function test_chatbot_reset_keeps_existing_reset_specific_fallback_text(): void
    {
        AppSetting::setVal('wa_status', 'true');
        AppSetting::setVal('llm_model_name', 'custom-model');
        $response = $this->postJson('/api/settings/chatbot/reset')->assertOk()
            ->assertJsonPath('settings.llm_model_name', 'qwen2.5:7b')
            ->assertJsonPath('settings.rag_num_ctx', 6144)
            ->assertJsonPath('settings.chatbot_fallback_message', 'Mohon maaf, informasi terkait hal tersebut belum tersedia di dalam dokumen SOP kami. Jika Anda ingin dibantu langsung oleh tim Diskominfotik, silakan beri tahu saya ya.');
        $this->assertSame(self::PROMPT_HASH, hash('sha256', $response->json('settings.rag_system_prompt')));
        $this->assertSame('true', AppSetting::getVal('wa_status'));
    }

    public function test_whatsapp_settings_normalize_url_encrypt_and_mask_token(): void
    {
        $this->postJson('/api/settings/whatsapp', [
            'wa_status' => true, 'wa_api_url' => 'gateway.example.test/send',
            'wa_token' => 'synthetic-wa-token', 'wa_phone_number' => '628123456789',
        ])->assertOk()->assertJsonPath('success', true);

        $this->assertSame('synthetic-wa-token', Crypt::decryptString(AppSetting::getVal('wa_token')));
        $this->getJson('/api/settings/whatsapp')->assertOk()
            ->assertJsonPath('wa_status', true)->assertJsonPath('wa_token', '••••••••••••')
            ->assertJsonPath('wa_api_url', 'https://gateway.example.test/send')
            ->assertJsonPath('wa_webhook_verify_token', 'diskominfo_wa_rag_token');
        Http::assertNothingSent();
    }

    public function test_masked_whatsapp_token_is_kept_and_omitted_token_is_cleared(): void
    {
        $encrypted = Crypt::encryptString('existing-wa-token');
        AppSetting::setVal('wa_token', $encrypted);
        $this->postJson('/api/settings/whatsapp', ['wa_status' => false, 'wa_token' => '••••••••••••'])->assertOk();
        $this->assertSame($encrypted, AppSetting::getVal('wa_token'));
        $this->postJson('/api/settings/whatsapp', ['wa_status' => false])->assertOk();
        $this->assertSame('', AppSetting::getVal('wa_token'));
    }

    public function test_invalid_whatsapp_settings_do_not_clear_saved_credentials(): void
    {
        $encrypted = Crypt::encryptString('existing-wa-token');
        AppSetting::setVal('wa_token', $encrypted);
        $this->postJson('/api/settings/whatsapp', ['wa_status' => true, 'wa_api_url' => '%invalid'])
            ->assertUnprocessable()->assertJsonValidationErrors(['wa_api_url']);
        $this->assertSame($encrypted, AppSetting::getVal('wa_token'));
    }

    public function test_whatsapp_connection_requires_configured_decryptable_token(): void
    {
        $this->postJson('/api/settings/whatsapp/test', ['target_phone' => '628123456789'])
            ->assertUnprocessable()->assertJsonPath('message', 'URL API atau Access Token WhatsApp belum dikonfigurasi.');
        AppSetting::setVal('wa_api_url', 'https://gateway.example.test/send');
        AppSetting::setVal('wa_token', 'invalid-ciphertext');
        $this->postJson('/api/settings/whatsapp/test', ['target_phone' => '628123456789'])
            ->assertStatus(500)->assertJsonPath('message', 'Gagal mendekripsi token WhatsApp yang tersimpan.');
        Http::assertNothingSent();
    }

    #[DataProvider('whatsappGateways')]
    public function test_whatsapp_connection_keeps_gateway_payload_and_response(string $url, bool $meta): void
    {
        AppSetting::setVal('wa_api_url', $url);
        AppSetting::setVal('wa_token', Crypt::encryptString('synthetic-wa-token'));
        Http::fake([$url => Http::response(['result' => 'accepted'])]);

        $this->postJson('/api/settings/whatsapp/test', [
            'target_phone' => '+62 8123456789', 'test_message' => 'Pesan pengujian',
        ])->assertOk()->assertJsonPath('gateway_response.result', 'accepted');
        Http::assertSent(function (Request $request) use ($meta) {
            return $meta
                ? $request->hasHeader('Authorization', 'Bearer synthetic-wa-token')
                    && $request['to'] === '628123456789' && $request['text']['body'] === 'Pesan pengujian'
                : $request->hasHeader('Authorization', 'synthetic-wa-token')
                    && $request['target'] === '+62 8123456789' && $request['message'] === 'Pesan pengujian';
        });
        Http::assertSentCount(1);
    }

    public static function whatsappGateways(): array
    {
        return [
            'generic' => ['https://gateway.example.test/send', false],
            'Meta' => ['https://graph.facebook.com/test/messages', true],
        ];
    }

    public function test_whatsapp_gateway_failure_keeps_502_and_error_message(): void
    {
        AppSetting::setVal('wa_api_url', 'https://gateway.example.test/send');
        AppSetting::setVal('wa_token', Crypt::encryptString('synthetic-wa-token'));
        Http::fake(['https://gateway.example.test/send' => Http::response(['error' => ['message' => 'Rate limited']], 429)]);
        $this->postJson('/api/settings/whatsapp/test', ['target_phone' => '628123456789'])
            ->assertStatus(502)->assertJsonPath('message', 'Gateway WhatsApp merespon dengan status 429: Rate limited');
    }

    public function test_telegram_read_masks_token_and_cleans_legacy_demo_username(): void
    {
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('synthetic-telegram-token'));
        AppSetting::setVal('telegram_bot_username', '@TesterDiskoBot');
        $this->getJson('/api/settings/telegram')->assertOk()
            ->assertJsonPath('telegram_bot_token', '••••••••••••')
            ->assertJsonPath('telegram_bot_username', '')->assertJsonPath('telegram_status', false);
        $this->assertSame('', AppSetting::getVal('telegram_bot_username'));
    }

    public function test_telegram_save_discovers_username_without_changing_token_contract(): void
    {
        Http::fake(['https://api.telegram.org/botsynthetic-telegram-token/getMe' => Http::response([
            'ok' => true, 'result' => ['username' => 'ActualBot'],
        ])]);
        $this->postJson('/api/settings/telegram', [
            'telegram_status' => true, 'telegram_bot_token' => 'synthetic-telegram-token',
            'telegram_bot_username' => '@SubmittedBot',
        ])->assertOk()->assertJsonPath('telegram_bot_username', '@ActualBot');
        $this->assertSame('synthetic-telegram-token', Crypt::decryptString(AppSetting::getVal('telegram_bot_token')));
        Http::assertSentCount(1);
    }

    public function test_telegram_masked_token_skips_discovery_and_omission_clears_token(): void
    {
        $encrypted = Crypt::encryptString('existing-telegram-token');
        AppSetting::setVal('telegram_bot_token', $encrypted);
        $this->postJson('/api/settings/telegram', [
            'telegram_status' => true, 'telegram_bot_token' => '••••••••••••',
        ])->assertOk();
        $this->assertSame($encrypted, AppSetting::getVal('telegram_bot_token'));
        $this->postJson('/api/settings/telegram', ['telegram_status' => false])->assertOk();
        $this->assertSame('', AppSetting::getVal('telegram_bot_token'));
        Http::assertNothingSent();
    }

    public function test_telegram_identity_and_message_tests_keep_distinct_responses(): void
    {
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('synthetic-telegram-token'));
        Http::fake([
            'https://api.telegram.org/*/getMe' => Http::response([
                'ok' => true, 'result' => ['first_name' => 'Sapa', 'username' => 'SapaTestBot'],
            ]),
            'https://api.telegram.org/*/sendMessage' => Http::response(['ok' => true, 'result' => ['message_id' => 7]]),
        ]);
        $this->postJson('/api/settings/telegram/test')->assertOk()->assertJsonPath('bot_info.username', 'SapaTestBot');
        $this->postJson('/api/settings/telegram/test', ['chat_id' => '12345', 'test_message' => 'Tes bot'])
            ->assertOk()->assertJsonPath('response.message_id', 7);
        Http::assertSent(fn (Request $request) => $request->method() === 'POST'
            && $request->data() === ['chat_id' => '12345', 'text' => 'Tes bot', 'parse_mode' => 'Markdown']);
        Http::assertSentCount(2);
    }

    public function test_telegram_webhook_checks_https_and_preserves_failure_mapping(): void
    {
        AppSetting::setVal('telegram_bot_token', Crypt::encryptString('synthetic-telegram-token'));
        Http::fake([
            'https://api.telegram.org/*/deleteWebhook' => Http::response(['ok' => true]),
            'https://api.telegram.org/*/setWebhook' => Http::response(['description' => 'Unauthorized'], 401),
        ]);
        $this->postJson('/api/settings/telegram/webhook', ['webhook_url' => 'http://example.test/hook'])
            ->assertUnprocessable();
        Http::assertNothingSent();
        $this->postJson('/api/settings/telegram/webhook', ['action' => 'delete'])
            ->assertOk()->assertJsonPath('message', 'Webhook Telegram berhasil dinonaktifkan.');
        $this->postJson('/api/settings/telegram/webhook', ['webhook_url' => 'https://example.test/hook'])
            ->assertUnprocessable()->assertJsonPath('message', 'Telegram menolak pendaftaran webhook: Token Bot Telegram salah atau belum disimpan di Web Admin. Silakan periksa kembali Token dari @BotFather lalu klik "Simpan Kredensial Telegram".');
        Http::assertSentCount(2);
    }

    public function test_model_catalog_preserves_classification_flags_and_active_selection(): void
    {
        AppSetting::setVal('llm_model_name', 'qwen3:8b');
        Http::fake(['*/api/tags' => Http::response(['models' => [
            ['name' => ''],
            ['name' => 'qwen2.5:3b', 'size' => 2 * 1024 ** 3],
            ['name' => 'qwen3:8b', 'size' => 5 * 1024 ** 3],
            ['name' => 'qwen3:14b', 'size' => 10 * 1024 ** 3],
            ['name' => 'qwen2.5vl:7b', 'size' => 6 * 1024 ** 3],
            ['name' => 'vision:3b'],
            ['name' => 'bge-m3'],
        ]])]);
        $this->getJson('/api/settings/models')->assertOk()->assertJsonCount(6, 'models')
            ->assertJsonPath('active_model', 'qwen3:8b')->assertJsonPath('models.0.tier', 'light')
            ->assertJsonPath('models.1.tier', 'medium')->assertJsonPath('models.1.is_active', true)
            ->assertJsonPath('models.2.tier', 'heavy')->assertJsonPath('models.3.tier', 'specialized')
            ->assertJsonPath('models.4.tier', 'light')->assertJsonPath('models.4.is_vision', true)
            ->assertJsonPath('models.5.is_embedding', true);
    }

    public function test_offline_model_catalog_keeps_existing_fallback_choices(): void
    {
        AppSetting::setVal('llm_model_name', 'qwen3:8b');
        Http::fake(['*/api/tags' => Http::response([], 503)]);
        $this->getJson('/api/settings/models')->assertOk()->assertJsonCount(2, 'models')
            ->assertJsonPath('models.0.name', 'qwen2.5:3b')->assertJsonPath('models.1.name', 'qwen3:8b')
            ->assertJsonPath('models.1.is_active', true);
    }

    public function test_hardware_proxy_preserves_live_data_and_selected_model(): void
    {
        Http::fake(['*/api/health/hardware*' => Http::response(['gpu' => ['available' => true], 'model' => 'chosen-model'])]);
        $this->getJson('/api/settings/hardware?model=chosen-model')->assertOk()
            ->assertExactJson(['success' => true, 'data' => ['gpu' => ['available' => true], 'model' => 'chosen-model']]);
        Http::assertSent(fn (Request $request) => $request['model'] === 'chosen-model' && (int) $request['nocache'] === 1);
    }

    public function test_offline_hardware_keeps_503_response(): void
    {
        Http::fake(['*/api/health/hardware*' => Http::response([], 503)]);
        $this->getJson('/api/settings/hardware')->assertStatus(503)->assertExactJson([
            'success' => false, 'message' => 'Layanan Python AI tidak dapat dihubungi untuk membaca diagnostik hardware.',
        ]);
    }

    public function test_benchmark_keeps_generation_options_and_metric_units(): void
    {
        AppSetting::setVal('llm_model_name', 'chosen-model');
        Http::fake(['*/api/generate' => Http::response([
            'eval_count' => 40, 'eval_duration' => 2000000000,
            'prompt_eval_duration' => 500000000, 'response' => "  Jawaban uji  \n",
        ])]);
        $response = $this->postJson('/api/settings/models/benchmark')->assertOk()
            ->assertJsonPath('model', 'chosen-model')->assertJsonPath('tokens_per_second', 20)
            ->assertJsonPath('eval_count', 40)->assertJsonPath('eval_duration_ms', 2000)
            ->assertJsonPath('time_to_first_token_ms', 500)->assertJsonPath('sample_output', 'Jawaban uji');
        $this->assertGreaterThanOrEqual(0, $response->json('total_duration_ms'));
        Http::assertSent(fn (Request $request) => $request['model'] === 'chosen-model'
            && $request['stream'] === false && $request['options'] === ['temperature' => 0.1, 'num_predict' => 40]);
    }

    public function test_benchmark_failure_keeps_existing_error_response(): void
    {
        Http::fake(['*/api/generate' => Http::response(['error' => 'Model missing'], 404)]);
        $this->postJson('/api/settings/models/benchmark', ['model' => 'missing-model'])->assertStatus(500)
            ->assertJsonPath('message', 'Ollama gagal mengeksekusi inferensi benchmark: Model missing');
    }

    private function chatbotPayload(): array
    {
        return [
            'chatbot_name' => 'SAPA Uji', 'chatbot_persona' => 'Asisten layanan',
            'rag_system_prompt' => 'Prompt uji', 'rag_temperature' => 0.4,
            'rag_top_k' => 5, 'rag_citation_enabled' => false,
        ];
    }
}
