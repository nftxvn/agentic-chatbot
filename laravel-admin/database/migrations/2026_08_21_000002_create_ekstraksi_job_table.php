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
        Schema::create('ekstraksi_job', function (Blueprint $table) {
            $table->unsignedBigInteger('document_id')->primary();
            $table->enum('status', ['antre', 'berjalan', 'jeda', 'menunggu_koreksi', 'selesai', 'gagal'])->default('antre');
            $table->boolean('jeda_diminta')->default(false);
            $table->integer('halaman_total')->default(0);
            $table->integer('halaman_selesai')->default(0);
            $table->text('petunjuk_format')->nullable();
            $table->text('pesan')->nullable();
            $table->timestamp('updated_at')->useCurrent()->useCurrentOnUpdate();

            $table->foreign('document_id')->references('id')->on('documents')->onDelete('cascade');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('ekstraksi_job');
    }
};
