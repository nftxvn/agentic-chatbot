<?php

namespace Tests\Feature;

use App\Models\ChatbotDirectory;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class DirectoryControllerTest extends TestCase
{
    use RefreshDatabase;

    public function test_store_validates_and_normalizes_directory_tasks(): void
    {
        $this->actingAs(User::factory()->create());

        $response = $this->postJson('/api/directories', [
            'nama_bidang' => 'Bidang Infrastruktur',
            'keywords' => 'server, jaringan',
            'lokasi' => 'Gedung C',
            'email' => 'infrastruktur@example.test',
            'layanan_utama' => 'Helpdesk TI',
            'daftar_tugas' => "Kelola server\n\nPantau jaringan\n",
        ]);

        $response->assertCreated()->assertJsonPath('data.daftar_tugas', [
            'Kelola server',
            'Pantau jaringan',
        ]);
        $this->assertDatabaseHas('chatbot_directories', [
            'nama_bidang' => 'Bidang Infrastruktur',
        ]);
    }

    public function test_store_rejects_invalid_email(): void
    {
        $this->actingAs(User::factory()->create());

        $this->postJson('/api/directories', [
            'nama_bidang' => 'Bidang Infrastruktur',
            'keywords' => 'server, jaringan',
            'lokasi' => 'Gedung C',
            'email' => 'not-an-email',
            'layanan_utama' => 'Helpdesk TI',
        ])->assertUnprocessable()->assertJsonValidationErrors(['email']);
    }

    public function test_update_validates_partial_payload(): void
    {
        $this->actingAs(User::factory()->create());
        $directory = ChatbotDirectory::create([
            'nama_bidang' => 'Bidang Infrastruktur',
            'keywords' => 'server',
            'lokasi' => 'Gedung C',
            'email' => 'infrastruktur@example.test',
            'layanan_utama' => 'Helpdesk TI',
        ]);

        $this->putJson('/api/directories/'.$directory->id, [
            'email' => 'updated@example.test',
        ])->assertOk()->assertJsonPath('data.email', 'updated@example.test');
    }

    public function test_missing_directory_returns_not_found_before_payload_validation(): void
    {
        $this->actingAs(User::factory()->create());

        $this->putJson('/api/directories/999999', [])->assertNotFound();
        $this->putJson('/api/directories/999999', ['email' => 'invalid'])->assertNotFound();
    }

    public function test_invalid_update_keeps_existing_directory_unchanged(): void
    {
        $this->actingAs(User::factory()->create());
        $directory = ChatbotDirectory::create([
            'nama_bidang' => 'Bidang Infrastruktur',
            'keywords' => 'server',
            'lokasi' => 'Gedung C',
            'email' => 'infrastruktur@example.test',
            'layanan_utama' => 'Helpdesk TI',
        ]);

        $this->putJson('/api/directories/'.$directory->id, ['email' => 'invalid'])
            ->assertUnprocessable()->assertJsonValidationErrors(['email']);

        $this->assertSame('infrastruktur@example.test', $directory->fresh()->email);
    }
}
