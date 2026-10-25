<?php

namespace Database\Seeders;

use App\Models\DocumentCategory;
use Illuminate\Database\Seeder;

class DocumentCategorySeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        DocumentCategory::updateOrCreate(
            ['name' => 'General (Bebas)'],
            [
                'description' => 'Dokumen umum tanpa format khusus.',
                'vision_prompt' => 'Transkripsikan seluruh konten yang ada di gambar dokumen ini ke dalam format Markdown secara rapi dan akurat.',
                'prompt_variables' => null,
                'ui_layout' => 'general',
                'vision_model' => null,
                'is_active' => true,
            ]
        );

        DocumentCategory::updateOrCreate(
            ['name' => 'SOP Flowchart'],
            [
                'description' => 'Standard Operating Procedure dengan tabel dan alur flowchart pelaksana.',
                'vision_prompt' => "Transkripsikan tabel SOP dan alur flowchart berikut ke dalam format tabel Markdown secara rapi dan lengkap sesuai kolom: No, Uraian Prosedur, Pelaksana, Kelengkapan, Waktu, Output, dan Keterangan.",
                'prompt_variables' => [
                    'job_titles' => ['Penelaah Teknis Kebijakan', 'JF Analis Keuangan Negara Ahli Muda/PPK', 'PA/KPA']
                ],
                'ui_layout' => 'flowchart',
                'vision_model' => null,
                'is_active' => true,
            ]
        );

        $this->command->info('Document categories seeded successfully.');
    }
}
