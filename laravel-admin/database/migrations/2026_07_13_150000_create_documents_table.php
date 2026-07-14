<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('documents', function (Blueprint $table) {
            $table->id();
            $table->string('title');                           // Nama dokumen
            $table->string('original_filename');                // Nama file asli
            $table->string('storage_path');                     // Path di storage
            $table->enum('status', ['pending', 'processing', 'completed', 'failed'])->default('pending');
            $table->enum('pdf_type', ['text', 'scanned', 'mixed', 'unknown'])->default('unknown');
            $table->text('error_message')->nullable();          // Pesan error jika gagal
            $table->integer('total_pages')->nullable();
            $table->integer('total_chunks')->nullable();
            $table->foreignId('uploaded_by')->constrained('users')->onDelete('cascade');
            $table->timestamp('processed_at')->nullable();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('documents');
    }
};
