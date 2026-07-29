<?php

namespace Database\Seeders;

use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class DocumentCategorySeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $sopPrompt = "Anda adalah analis SOP pemerintah. Tentukan siapa PELAKSANA untuk tiap langkah prosedur di bawah.\n"
            . "DAFTAR JABATAN YANG TERSEDIA: {JOB_TITLES}\n\n"
            . "ATURAN DEDUKSI:\n"
            . "1. Jika uraian berbunyi 'menyerahkan kepada [Jabatan X]', maka pelaksananya BUKAN Jabatan X. "
            . "Pelaksananya adalah pihak yang AKTIF melakukan pekerjaan (menyusun, menyiapkan, memperbanyak, dst).\n"
            . "2. Jabatan yang MENERIMA dokumen di satu langkah akan menjadi PELAKSANA di langkah berikutnya.\n"
            . "3. Gunakan HANYA nama jabatan dari daftar di atas, jangan buat nama baru.\n\n"
            . "URAIAN PROSEDUR:\n{TEXT}\n\n"
            . "Jawab dengan JSON dictionary, key = nomor langkah (string), value = nama jabatan pelaksana.\n"
            . "Output HANYA JSON, tanpa penjelasan.";

        \App\Models\DocumentCategory::insert([
            [
                'name' => 'General (Bebas)',
                'description' => 'Dokumen umum tanpa format khusus.',
                'vision_prompt' => 'Transkripsikan seluruh konten yang ada di gambar dokumen ini ke dalam format Markdown secara rapi dan akurat.',
                'llm_prompt' => "Rapikan dan perbaiki hasil transkripsi dokumen (Markdown) berikut dari kesalahan ketik (typo) akibat proses OCR.\nOutput LANGSUNG berupa teks Markdown yang sudah diperbaiki, tanpa pengantar atau penjelasan apapun.\n\nTeks:\n---\n{TEXT}\n---",
                'prompt_variables' => null,
                'ui_layout' => 'general',
                'created_at' => now(),
                'updated_at' => now(),
            ],
            [
                'name' => 'SOP Flowchart',
                'description' => 'Standard Operating Procedure dengan tabel dan alur flowchart pelaksana.',
                'vision_prompt' => "Anda adalah editor teks. Perbaiki typo dan kesalahan OCR pada tabel Markdown berikut.\n"
                                  . "PENTING:\n"
                                  . "- JANGAN UBAH kolom 'No' dan kolom 'Pelaksana' sama sekali\n"
                                  . "- Hanya perbaiki typo di kolom Uraian Prosedur, Kelengkapan, Waktu, Output, dan Ket\n"
                                  . "- Jangan ubah struktur tabel Markdown\n"
                                  . "- Jangan rangkum, potong, atau tambah konten\n"
                                  . "- Output LANGSUNG berupa tabel yang sudah diperbaiki tanpa penjelasan apapun\n\n"
                                  . "Teks:\n---\n{TEXT}\n---",
                'llm_prompt' => $sopPrompt,
                'prompt_variables' => json_encode([
                    'job_titles' => ['Penelaah Teknis Kebijakan', 'JF Analis Keuangan Negara Ahli Muda/PPK', 'PA/KPA']
                ]),
                'ui_layout' => 'flowchart',
                'created_at' => now(),
                'updated_at' => now(),
            ]
        ]);
    }
}
