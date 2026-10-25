<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('document_vector_cleanups', function (Blueprint $table): void {
            $table->id();
            // No cascading FK: cleanup must survive deletion of the document.
            $table->unsignedBigInteger('document_id');
            // Empty token means all vectors; starts wait until this job finishes.
            $table->string('operation_token', 64)->default('');
            $table->unsignedInteger('attempts')->default(0);
            $table->text('last_error')->nullable();
            $table->timestamp('available_at')->index();
            $table->timestamps();
            $table->unique(['document_id', 'operation_token'], 'document_vector_cleanup_scope');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('document_vector_cleanups');
    }
};
