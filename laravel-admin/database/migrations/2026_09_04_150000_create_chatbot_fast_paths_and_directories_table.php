<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        // 1. Tabel Fast-Path FAQ & Jawaban Instan
        Schema::create('chatbot_fast_paths', function (Blueprint $table) {
            $table->id();
            $table->string('category', 50)->default('general'); // general, layanan, sop, faq
            $table->string('title', 150);
            $table->text('keywords'); // kata kunci pencocokan, dipisahkan koma
            $table->longText('response_text');
            $table->boolean('is_active')->default(true);
            $table->integer('sort_order')->default(0);
            $table->timestamps();

            $table->index(['is_active', 'category']);
        });

        // 2. Tabel Direktori Unit Kerja & Bidang
        Schema::create('chatbot_directories', function (Blueprint $table) {
            $table->id();
            $table->string('nama_bidang', 150);
            $table->text('keywords'); // kata kunci pencocokan, dipisahkan koma
            $table->string('lokasi', 255);
            $table->string('email', 100);
            $table->string('layanan_utama', 150);
            $table->text('daftar_tugas')->nullable(); // JSON list tugas
            $table->string('jam_operasional', 100)->default('Senin - Jumat (08:00 - 16:45 WIB)');
            $table->boolean('is_active')->default(true);
            $table->integer('sort_order')->default(0);
            $table->timestamps();

            $table->index('is_active');
        });

        // Seed default initial data
        $now = now();
        DB::table('chatbot_fast_paths')->insert([
            [
                'category'      => 'general',
                'title'         => 'Profil Kepala Dinas',
                'keywords'      => 'kepala dinas, siapa kadis, kadis kominfotik, kadis kominfo, pimpinan diskominfotik, nama kepala dinas',
                'response_text' => 'Kepala Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh saat ini dijabat oleh Bapak **Alizar, S.Ag., M.Hum**.',
                'is_active'     => true,
                'sort_order'    => 1,
                'created_at'    => $now,
                'updated_at'    => $now,
            ],
            [
                'category'      => 'general',
                'title'         => 'Alamat & Lokasi Kantor',
                'keywords'      => 'alamat kantor, lokasi kantor, dimana alamat, alamat diskominfotik, lokasi diskominfotik, dimana kantor kominfotik, alamat kominfo banda aceh',
                'response_text' => "Kantor Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh beralamat di:\n\n**Kompleks Balai Kota Banda Aceh (Gedung C Lantai 3)**\nJl. Tgk. Abu Lam U No. 7, Gampong Kp. Baru, Kec. Baiturrahman, Kota Banda Aceh, Aceh 23116.",
                'is_active'     => true,
                'sort_order'    => 2,
                'created_at'    => $now,
                'updated_at'    => $now,
            ],
            [
                'category'      => 'general',
                'title'         => 'Kontak Resmi & Website',
                'keywords'      => 'email diskominfotik, website diskominfotik, nomor telepon diskominfotik, kontak resmi diskominfotik, call center 112, kontak email',
                'response_text' => "Kontak resmi Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh:\n\n- **Email Resmi:** diskominfotik@bandaacehkota.go.id\n- **Website Resmi:** https://diskominfotik.bandaacehkota.go.id\n- **Portal Satu Data:** https://data.bandaacehkota.go.id\n- **Call Center Darurat:** 112 (Banda Aceh Siaga)\n- **Lokasi:** Balai Kota Banda Aceh (Gedung C Lantai 3), Jl. Tgk. Abu Lam U No. 7",
                'is_active'     => true,
                'sort_order'    => 3,
                'created_at'    => $now,
                'updated_at'    => $now,
            ],
            [
                'category'      => 'general',
                'title'         => 'Jam Operasional Kantor',
                'keywords'      => 'jam kerja, jam operasional, jam buka, jam layanan, hari kerja kantor, jadwal pelayanan kantor',
                'response_text' => "Jam operasional pelayanan administrasi dan Front Office Diskominfotik Kota Banda Aceh:\n\n- **Senin - Kamis:** Pukul 08:00 - 16:45 WIB (Istirahat: 12:30 - 14:00 WIB)\n- **Jumat:** Pukul 08:00 - 16:45 WIB (Istirahat: 12:00 - 14:00 WIB)\n- **Sabtu & Minggu:** Libur (Tutup)\n\nPelayanan darurat Call Center 112 beroperasi selama 24 jam setiap hari.",
                'is_active'     => true,
                'sort_order'    => 4,
                'created_at'    => $now,
                'updated_at'    => $now,
            ],
            [
                'category'      => 'general',
                'title'         => 'Prosedur Magang & PKL Mahasiswa',
                'keywords'      => 'magang, pkl, kerja praktik, magang mahasiswa, syarat magang, pengajuan magang, magang di kominfo',
                'response_text' => "Untuk permohonan Magang / Praktik Kerja Lapangan (PKL) di Diskominfotik Kota Banda Aceh:\n\n1. Pemohon mengajukan **Surat Pengantar Resmi** dari Kampus / Sekolah yang ditujukan kepada Kepala Dinas Kominfotik Kota Banda Aceh.\n2. Menyertakan proposal magang / curriculum vitae singkat dan fotokopi KTM/KTP.\n3. Surat diserahkan ke bagian **Sekretariat (Gedung C Lantai 3 Balai Kota Banda Aceh)** atau dikirim via email: diskominfotik@bandaacehkota.go.id.\n4. Konfirmasi penerimaan dan penempatan bidang akan diberitahukan dalam 3-5 hari kerja.",
                'is_active'     => true,
                'sort_order'    => 5,
                'created_at'    => $now,
                'updated_at'    => $now,
            ],
        ]);

        DB::table('chatbot_directories')->insert([
            [
                'nama_bidang'     => 'Bidang Tata Kelola E-Government',
                'keywords'        => 'egov, e-gov, domain, hosting, aplikasi, vps, server, spbe, email asn, website pemko',
                'lokasi'          => 'Gedung C Lantai 3 Balai Kota Banda Aceh',
                'email'           => 'egov@bandaacehkota.go.id',
                'layanan_utama'   => 'Helpdesk SPBE, Domain/Hosting & Infrastruktur TI',
                'daftar_tugas'    => json_encode([
                    'Pengelolaan domain dan subdomain *.bandaacehkota.go.id',
                    'Penyediaan web hosting dan Virtual Private Server (VPS) OPD',
                    'Pengembangan, pemeliharaan, dan integrasi aplikasi SPBE',
                    'Pengelolaan jaringan intra pemerintah dan akses internet Pemko',
                ]),
                'jam_operasional' => 'Senin - Jumat (08:00 - 16:45 WIB)',
                'is_active'       => true,
                'sort_order'      => 1,
                'created_at'      => $now,
                'updated_at'      => $now,
            ],
            [
                'nama_bidang'     => 'Bidang Informasi dan Komunikasi Publik (IKP)',
                'keywords'        => 'ikp, informasi, komunikasi, publik, ppid, berita, lapor, media, liputan, medsos',
                'lokasi'          => 'Gedung C Lantai 3 Balai Kota Banda Aceh',
                'email'           => 'ikp@bandaacehkota.go.id',
                'layanan_utama'   => 'Front Office PPID Utama & Media Center',
                'daftar_tugas'    => json_encode([
                    'Pelayanan Permohonan Informasi Publik melalui PPID Utama',
                    'Pengelolaan Media Center dan peliputan kegiatan Pemerintah Kota',
                    'Pengelolaan saluran pengaduan masyarakat SP4N-LAPOR!',
                    'Publikasi berita dan pengelolaan media sosial resmi Pemko',
                ]),
                'jam_operasional' => 'Senin - Jumat (08:00 - 16:45 WIB)',
                'is_active'       => true,
                'sort_order'      => 2,
                'created_at'      => $now,
                'updated_at'      => $now,
            ],
            [
                'nama_bidang'     => 'Bidang Statistik dan Persandian',
                'keywords'        => 'statistik, persandian, sandi, tte, sertifikat, csirt, keamanan, data, satu data',
                'lokasi'          => 'Gedung C Lantai 3 Balai Kota Banda Aceh',
                'email'           => 'statistik.persandian@bandaacehkota.go.id',
                'layanan_utama'   => 'Helpdesk TTE BSrE & Layanan Satu Data',
                'daftar_tugas'    => json_encode([
                    'Pengelolaan portal Satu Data Banda Aceh (data.bandaacehkota.go.id)',
                    'Rekomendasi kegiatan statistik sektoral (ROMANIK)',
                    'Fasilitasi penerbitan Tanda Tangan Elektronik (TTE BSrE / BSSN)',
                    'Pengamanan persandian dan penanganan insiden siber (Banda Aceh CSIRT)',
                ]),
                'jam_operasional' => 'Senin - Jumat (08:00 - 16:45 WIB)',
                'is_active'       => true,
                'sort_order'      => 3,
                'created_at'      => $now,
                'updated_at'      => $now,
            ],
            [
                'nama_bidang'     => 'Sekretariat & Informasi Umum',
                'keywords'        => 'sekretariat, tata usaha, persuratan, kepegawaian, keuangan, magang, pkl, umum',
                'lokasi'          => 'Gedung C Lantai 3 Balai Kota Banda Aceh, Jl. Tgk. Abu Lam U No. 7',
                'email'           => 'diskominfotik@bandaacehkota.go.id',
                'layanan_utama'   => 'Front Desk Sekretariat & Administrasi Umum',
                'daftar_tugas'    => json_encode([
                    'Pelayanan administrasi persuratan dan ketatausahaan',
                    'Pengelolaan kepegawaian dan koordinasi magang/PKL mahasiswa',
                    'Perencanaan program, keuangan, dan aset instansi',
                    'Penerimaan tamu dinas dan konsultasi umum',
                ]),
                'jam_operasional' => 'Senin - Jumat (08:00 - 16:45 WIB)',
                'is_active'       => true,
                'sort_order'      => 4,
                'created_at'      => $now,
                'updated_at'      => $now,
            ],
        ]);
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('chatbot_directories');
        Schema::dropIfExists('chatbot_fast_paths');
    }
};
