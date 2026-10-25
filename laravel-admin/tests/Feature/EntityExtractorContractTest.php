<?php

namespace Tests\Feature;

use App\Models\ChatTicket;
use App\Services\EntityExtractorService as Extractor;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Redis;
use Illuminate\Support\Str;
use Mockery;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class EntityExtractorContractTest extends TestCase
{
    use RefreshDatabase;

    public static function textCases(): array
    {
        return [
            'structured' => ['Nama: Budi Santoso | Instansi: Dinkes | Kendala: akun terkunci | WA: 081234567890', null,
                ['name' => 'Budi Santoso', 'agency' => 'Dinas Kesehatan', 'issue_summary' => 'akun terkunci', 'contact' => '081234567890']],
            'natural' => ['Saya Budi dari dinkes ingin reset akun', null,
                ['name' => 'Budi', 'agency' => 'Dinas Kesehatan', 'issue_summary' => 'reset akun', 'contact' => null]],
            'longest alias' => ['Budi dari UIN Ar-Raniry ingin konsultasi', null,
                ['name' => 'Budi', 'agency' => 'UIN Ar-Raniry', 'issue_summary' => 'konsultasi', 'contact' => null]],
            'greeting' => ['halo', null, ['name' => null, 'agency' => null, 'issue_summary' => null, 'contact' => null]],
            'profile' => ['halo', 'SITI AMINAH', ['name' => 'Siti Aminah', 'agency' => null, 'issue_summary' => null, 'contact' => null]],
            'generic profile' => ['halo', 'DefaultUser', ['name' => null, 'agency' => null, 'issue_summary' => null, 'contact' => null]],
            'null profile' => ['halo', 'null', ['name' => null, 'agency' => null, 'issue_summary' => null, 'contact' => null]],
        ];
    }

    #[DataProvider('textCases')]
    public function test_text_parsing_preserves_entities_and_profile_policy(string $text, ?string $profile, array $expected): void
    {
        $this->assertSame($expected, Extractor::extractFromText($text, $profile));
    }

    public function test_name_and_agency_normalization_keep_stopword_boundaries_and_alias_suffixes(): void
    {
        $this->assertSame('Budi Santoso', Extractor::cleanName('  Bapak BUDI SANTOSO dari Dinkes  '));
        $this->assertSame('Budi Siti Ahmad Yusuf', Extractor::cleanName('Budi Siti Ahmad Yusuf Zainal'));
        $this->assertNull(Extractor::cleanName('hubungkan dengan admin'));
        $this->assertSame('Dinas Kesehatan Aceh', Extractor::cleanAgency('dari dinkes aceh'));
        $this->assertSame('DPMPTSP', Extractor::cleanAgency('dpmptsp'));
        $this->assertSame('Dinas SOP Dan SPPD', Extractor::cleanAgency('Dinas sop dan sppd'));
    }

    public function test_empty_session_skips_redis_and_keeps_distinct_profile_policy(): void
    {
        Redis::shouldReceive('connection')->never();
        $this->assertSame(['name' => 'User', 'agency' => null, 'issue_summary' => null, 'contact' => null],
            Extractor::extractFromSessionHistory('', 'User'));
    }

    public function test_session_history_reads_database_two_and_keeps_first_nonempty_entity_per_field(): void
    {
        $this->fakeSession([
            ['role' => 'assistant', 'content' => 'Nama: Salah | Instansi: Disdik'],
            ['role' => 'user', 'content' => '  '],
            ['role' => 'user', 'content' => 'halo'],
            ['role' => 'user', 'content' => 'Nama: Budi | Instansi: Dinkes'],
            ['role' => 'user', 'content' => 'Kendala: akses gagal | WA: 081234567890'],
            ['role' => 'user', 'content' => 'Nama: Siti | Instansi: Disdik | Kendala: masalah berikutnya'],
        ]);

        $this->assertSame(['name' => 'Budi', 'agency' => 'Dinas Kesehatan', 'issue_summary' => 'akses gagal', 'contact' => '081234567890'],
            Extractor::extractFromSessionHistory('synthetic-session'));
    }

    public function test_profile_extracted_from_earlier_turn_is_not_replaced_by_later_name(): void
    {
        $this->fakeSession([['role' => 'user', 'content' => 'halo'], ['role' => 'user', 'content' => 'Nama: Budi']]);

        $this->assertSame('Profil Awal', Extractor::extractFromSessionHistory('synthetic-session', 'Profil Awal')['name']);
    }

    public function test_first_substantive_inquiry_is_used_when_no_explicit_issue_was_extracted(): void
    {
        $inquiry = str_repeat('Bagaimana proses permohonan informasi? ', 8);
        $this->fakeSession([
            ['role' => 'user', 'content' => 'halo'],
            ['role' => 'user', 'content' => 'hubungi admin'],
            ['role' => 'user', 'content' => $inquiry],
        ]);

        $this->assertSame('Pertanyaan: '.Str::limit(trim($inquiry), 140),
            Extractor::extractFromSessionHistory('synthetic-session')['issue_summary']);
    }

    public function test_malformed_session_json_keeps_fallback_and_does_not_throw(): void
    {
        $connection = Mockery::mock();
        Redis::shouldReceive('connection')->once()->andReturn($connection);
        $connection->shouldReceive('select')->once()->with(2);
        $connection->shouldReceive('get')->once()->with('chatbot:session:synthetic-session')->andReturn('{broken');

        $this->assertSame(['name' => 'Profil', 'agency' => null, 'issue_summary' => null, 'contact' => null],
            Extractor::extractFromSessionHistory('synthetic-session', 'Profil'));
    }

    public function test_redis_extension_error_is_caught_as_throwable_and_profile_fallback_remains_available(): void
    {
        Redis::shouldReceive('connection')->once()->andThrow(new \Error('synthetic unavailable extension'));
        Log::spy();

        $this->assertSame('Profil', Extractor::extractFromSessionHistory('synthetic-session', 'Profil')['name']);
        Log::shouldHaveReceived('warning')->once()->with('EntityExtractorService: Gagal membaca Redis session synthetic-session: synthetic unavailable extension');
    }

    public function test_session_null_profile_policy_remains_distinct_from_text_profile_policy(): void
    {
        $this->fakeSession([]);
        $this->assertSame('Null', Extractor::extractFromSessionHistory('synthetic-session', 'null')['name']);
    }

    public function test_enrichment_relabels_only_generic_citizen_messages_and_does_not_update_contact(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'enrich-session', 'citizen_name' => 'Warga', 'issue_summary' => 'Hubungi admin']);
        $generic = $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Warga', 'message' => 'halo']);
        $named = $ticket->messages()->create(['sender_type' => 'citizen', 'sender_name' => 'Nama Lama', 'message' => 'halo']);
        $agent = $ticket->messages()->create(['sender_type' => 'agent', 'sender_name' => 'Warga', 'message' => 'balasan']);

        $this->assertTrue(Extractor::enrichTicket($ticket, 'Nama: Budi | Instansi: Dinkes | Kendala: akun terkunci | WA: 081234567890'));
        $this->assertSame('Budi', $generic->fresh()->sender_name);
        $this->assertSame('Nama Lama', $named->fresh()->sender_name);
        $this->assertSame('Warga', $agent->fresh()->sender_name);
        $this->assertSame('Dinas Kesehatan', $ticket->fresh()->citizen_agency);
        $this->assertSame('akun terkunci', $ticket->issue_summary);
        $this->assertNull($ticket->citizen_contact);
    }

    public function test_enrichment_preserves_specific_issue_without_explicit_issue_key(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'specific-session', 'citizen_name' => 'Budi',
            'citizen_agency' => 'Dinas Kesehatan', 'issue_summary' => 'Reset akun portal SPBE']);

        $this->assertFalse(Extractor::enrichTicket($ticket, 'ingin mengubah kata sandi', 'Profil Lain'));
        $this->assertSame('Budi', $ticket->fresh()->citizen_name);
        $this->assertSame('Reset akun portal SPBE', $ticket->issue_summary);
    }

    public function test_enrichment_uses_coordination_summary_for_generic_issue_with_known_identity(): void
    {
        $ticket = ChatTicket::create(['session_id' => 'coordination-session', 'citizen_name' => 'Budi',
            'citizen_agency' => 'Dinas Kesehatan', 'issue_summary' => 'halo']);

        $this->assertTrue(Extractor::enrichTicket($ticket, 'halo'));
        $this->assertSame('Bantuan koordinasi untuk Budi (Dinas Kesehatan)', $ticket->fresh()->issue_summary);
    }

    public function test_inherited_parser_keeps_existing_self_binding_for_overridden_helpers(): void
    {
        $subclass = new class extends Extractor {
            public static function cleanName(?string $raw): ?string
            {
                return 'Override';
            }
        };

        $this->assertSame('Override', $subclass::cleanName('Budi'));
        $this->assertSame('Budi', $subclass::extractFromText('Nama: Budi')['name']);
    }

    private function fakeSession(array $messages): void
    {
        $connection = Mockery::mock();
        Redis::shouldReceive('connection')->once()->andReturn($connection);
        $connection->shouldReceive('select')->once()->with(2)->ordered();
        $connection->shouldReceive('get')->once()->with('chatbot:session:synthetic-session')
            ->andReturn(json_encode(['messages' => $messages]))->ordered();
    }
}
