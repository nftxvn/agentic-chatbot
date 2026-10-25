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
        if (DB::getDriverName() === 'mysql') {
            DB::statement("ALTER TABLE document_logs MODIFY COLUMN action VARCHAR(50) NOT NULL");
        } elseif (DB::getDriverName() === 'sqlite') {
            Schema::table('document_logs', function (Blueprint $table) {
                $table->string('action', 50)->change();
            });
        }
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        if (DB::getDriverName() === 'mysql') {
            DB::statement("ALTER TABLE document_logs MODIFY COLUMN action ENUM('uploaded', 'processing', 'ocr_started', 'embedding_started', 'completed', 'failed', 'replaced') NOT NULL");
        } elseif (DB::getDriverName() === 'sqlite') {
            Schema::table('document_logs', function (Blueprint $table) {
                $table->enum('action', ['uploaded', 'processing', 'ocr_started', 'embedding_started', 'completed', 'failed', 'replaced'])->change();
            });
        }
    }
};
