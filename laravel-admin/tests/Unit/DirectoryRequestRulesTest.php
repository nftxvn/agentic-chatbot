<?php

namespace Tests\Unit;

use App\Http\Requests\DirectoryStoreRequest;
use App\Http\Requests\DirectoryUpdateRequest;
use PHPUnit\Framework\TestCase;

class DirectoryRequestRulesTest extends TestCase
{
    public function test_store_request_requires_the_directory_identity_fields(): void
    {
        $rules = (new DirectoryStoreRequest())->rules();

        foreach (['nama_bidang', 'keywords', 'lokasi', 'email', 'layanan_utama'] as $field) {
            $this->assertStringContainsString('required', $rules[$field]);
        }
    }

    public function test_update_request_allows_partial_updates_but_validates_supplied_fields(): void
    {
        $rules = (new DirectoryUpdateRequest())->rules();

        foreach (['nama_bidang', 'keywords', 'lokasi', 'email', 'layanan_utama'] as $field) {
            $this->assertStringContainsString('sometimes', $rules[$field]);
            $this->assertStringContainsString('required', $rules[$field]);
        }
    }
}
