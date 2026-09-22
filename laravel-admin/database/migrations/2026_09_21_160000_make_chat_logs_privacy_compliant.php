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
        Schema::table('chat_logs', function (Blueprint $table) {
            $table->text('query')->nullable()->change();
            $table->longText('answer')->nullable()->change();
            $table->string('sender_identifier', 100)->nullable()->change();
        });

        // Hapus teks pesan sensitif lama agar langsung patuh privasi
        DB::table('chat_logs')->update([
            'query' => null,
            'answer' => null,
            'sender_identifier' => DB::raw("CASE WHEN channel = 'whatsapp' THEN 'Pengguna WhatsApp' WHEN channel = 'telegram' THEN 'Pengguna Telegram' ELSE sender_identifier END"),
        ]);
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('chat_logs', function (Blueprint $table) {
            $table->text('query')->nullable(false)->change();
        });
    }
};
