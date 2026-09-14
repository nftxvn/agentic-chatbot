<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        DB::statement("ALTER TABLE document_logs MODIFY COLUMN action VARCHAR(50) NOT NULL");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        DB::statement("ALTER TABLE document_logs MODIFY COLUMN action ENUM('uploaded', 'processing', 'ocr_started', 'embedding_started', 'completed', 'failed', 'replaced') NOT NULL");
    }
};
