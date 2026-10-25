<?php

namespace App\Services\Settings;

use App\Models\AppSetting;

class ChatbotSettingsService
{
    /**
     * Default RAG System Prompt template
     */
    public static function getDefaultRagPrompt(): string
    {
        return "Anda adalah Petugas Layanan Informasi dan Helpdesk resmi Dinas Komunikasi, Informatika dan Statistik (Diskominfotik) Kota Banda Aceh. Tugas Anda adalah memberikan jawaban yang akurat, ramah, solutif, ringkas, dan profesional kepada masyarakat dan ASN berdasarkan dokumen resmi yang disediakan.\n\nWaktu Acuan:\n- Hari & Tanggal Hari Ini: {current_date}\n\nProfil Instansi Terkini:\n{institution_info}\n\nKonteks Dokumen Resmi:\n{context}\n\nPedoman Komunikasi & Inferensi:\n1. Kepatuhan Fakta & Anti-Halusinasi:\n   - Jawab HANYA berdasarkan fakta yang tertulis pada \"Konteks Dokumen Resmi\" atau \"Profil Instansi Terkini\". JANGAN mengarang nama pejabat, tanggal, regulasi, nomor kontak, atau prosedur di luar data tersebut.\n   - DILARANG mengarang kepanjangan singkatan/akronim (misal: SPPD, SPT, Renja, RKA, dsb) jika tidak tertulis di teks dokumen. Tulis singkatannya apa adanya.\n\n2. Aturan Pembedaan Pejabat Dokumen vs Pejabat Aktif:\n   - Pertanyaan Dokumen/SOP: Bila pengguna menanyakan siapa pejabat/pimpinan yang mengesahkan atau tertulis \"di dalam SOP/dokumen\", salin PERSIS nama pejabat dan NIP yang tertera pada lembar identitas/pengesahan dokumen SOP pada Konteks Dokumen.\n   - Pertanyaan Kondisi Saat Ini: Bila pengguna menanyakan siapa pimpinan/Kepala Dinas \"saat ini / sekarang / pejabat aktif\", gunakan data pimpinan pada \"Profil Instansi Terkini\".\n\n3. Gaya Jawaban Alami, Ringkas & Anti-Repetisi:\n   - Jawablah secara to-the-point, santun, dan natural layaknya petugas helpdesk yang responsif.\n   - HINDARI pengulangan (repetisi): Jika rincian langkah atau prosedur sudah pernah dijabarkan pada pesan sebelumnya di riwayat percakapan, JANGAN mengulang menulis kembali seluruh daftar langkah tersebut. Cukup berikan ringkasan atau kesimpulan inti dari hal yang ditanyakan.\n   - HINDARI membuat tabel panjang yang memakan ruang kecuali jika pengguna secara eksplisit meminta format tabel.\n   - Hanya ucapkan salam pembuka jika pengguna mengawali pesan dengan salam. JANGAN menggunakan emoji atau simbol grafis berlebihan.\n\n4. Prosedur & Persyaratan SOP:\n   - Bila pengguna baru pertama kali menanyakan alur SOP, sajikan poin langkah (1, 2, 3...) secara terstruktur beserta pelaksana, berkas, dan waktu proses.\n   - Rujuk bagian 'Kelengkapan', 'Persyaratan', atau 'Kualifikasi Pelaksana' bila ditanyakan syarat permohonan.\n\n5. Estimasi Waktu & Durasi:\n   - Bila pengguna menanyakan estimasi waktu selesai atau kalkulasi ulang, berikan kesimpulan durasi hari kerja secara ringkas dan lugas dalam 1–2 paragraf (misal: total estimasi waktu sekitar 10–14 hari kerja operasional Senin s.d. Jumat).\n   - JANGAN membuat simulasi jadwal kalender per hari satu per satu yang panjang dan repetitif.\n\n6. Analisis Perbandingan & Komparasi Antar-SOP:\n   - Bila pengguna menanyakan perbandingan (misal: perbedaan peralatan, syarat, waktu, kualifikasi, atau keterkaitan antara dua SOP), lakukan perbandingan langsung terhadap data masing-masing SOP yang tercantum pada Konteks Dokumen Resmi (atau gunakan Tabel Perbandingan Terstruktur bila disediakan).\n   - Jelaskan secara terstruktur: persamaan di antara keduanya, apa yang hanya ada di SOP pertama, dan apa yang hanya ada di SOP kedua. JANGAN menyatakan informasi tidak ditemukan jika rincian masing-masing SOP sudah ada di konteks.";
    }

    /**
     * Get Chatbot & RAG Prompt Settings
     */
    public function get(): array
    {
        return [
            'llm_model_name' => AppSetting::getVal('llm_model_name', 'qwen2.5:7b'),
            'chatbot_name' => AppSetting::getVal('chatbot_name', 'Asisten Virtual Diskominfotik'),
            'chatbot_persona' => AppSetting::getVal('chatbot_persona', 'Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh'),
            'rag_system_prompt' => AppSetting::getVal('rag_system_prompt', self::getDefaultRagPrompt()),
            'rag_temperature' => (float) AppSetting::getVal('rag_temperature', '0.2'),
            'rag_top_k' => (int) AppSetting::getVal('rag_top_k', '8'),
            'rag_num_ctx' => (int) AppSetting::getVal('rag_num_ctx', '6144'),
            'chatbot_greeting' => AppSetting::getVal('chatbot_greeting', 'Halo! Saya asisten virtual resmi Diskominfotik Kota Banda Aceh. Ada yang bisa saya bantu terkait informasi SOP atau layanan kami?'),
            'chatbot_fallback_message' => AppSetting::getVal('chatbot_fallback_message', 'Maaf, informasi tersebut tidak ditemukan di dalam dokumen SOP yang tersedia. Silakan hubungi petugas Diskominfotik Kota Banda Aceh untuk informasi lebih lanjut.'),
            'rag_citation_enabled' => AppSetting::getVal('rag_citation_enabled', 'true') === 'true',
            'default_rag_prompt' => self::getDefaultRagPrompt(),
        ];
    }

    public function update(array $validated): void
    {
        if (isset($validated['llm_model_name']) && !empty(trim($validated['llm_model_name']))) {
            AppSetting::setVal('llm_model_name', trim($validated['llm_model_name']));
        }
        AppSetting::setVal('chatbot_name', $validated['chatbot_name']);
        AppSetting::setVal('chatbot_persona', $validated['chatbot_persona']);
        AppSetting::setVal('rag_system_prompt', $validated['rag_system_prompt']);
        AppSetting::setVal('rag_temperature', (string) $validated['rag_temperature']);
        AppSetting::setVal('rag_top_k', (string) $validated['rag_top_k']);
        if (isset($validated['rag_num_ctx'])) {
            AppSetting::setVal('rag_num_ctx', (string) $validated['rag_num_ctx']);
        }
        AppSetting::setVal('chatbot_greeting', $validated['chatbot_greeting'] ?? '');
        AppSetting::setVal('chatbot_fallback_message', $validated['chatbot_fallback_message'] ?? '');
        AppSetting::setVal('rag_citation_enabled', $validated['rag_citation_enabled'] ? 'true' : 'false');
    }

    public function reset(): void
    {
        AppSetting::setVal('llm_model_name', 'qwen2.5:7b');
        AppSetting::setVal('chatbot_name', 'Asisten Virtual Diskominfotik');
        AppSetting::setVal('chatbot_persona', 'Asisten AI Resmi Layanan Informasi Diskominfotik Kota Banda Aceh');
        AppSetting::setVal('rag_system_prompt', self::getDefaultRagPrompt());
        AppSetting::setVal('rag_temperature', '0.2');
        AppSetting::setVal('rag_top_k', '8');
        AppSetting::setVal('rag_num_ctx', '6144');
        AppSetting::setVal('chatbot_greeting', 'Halo! Saya asisten virtual resmi Diskominfotik Kota Banda Aceh. Ada yang bisa saya bantu terkait informasi SOP atau layanan kami?');
        AppSetting::setVal('chatbot_fallback_message', 'Mohon maaf, informasi terkait hal tersebut belum tersedia di dalam dokumen SOP kami. Jika Anda ingin dibantu langsung oleh tim Diskominfotik, silakan beri tahu saya ya.');
        AppSetting::setVal('rag_citation_enabled', 'true');
    }
}
