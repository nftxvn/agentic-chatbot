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
        Schema::create('ekstraksi_halaman', function (Blueprint $table) {
            $table->unsignedBigInteger('document_id');
            $table->integer('page_number');
            $table->longText('text');
            $table->boolean('diperiksa')->default(false);
            $table->timestamp('created_at')->useCurrent();

            $table->primary(['document_id', 'page_number']);
            $table->foreign('document_id')->references('id')->on('documents')->onDelete('cascade');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('ekstraksi_halaman');
    }
};
