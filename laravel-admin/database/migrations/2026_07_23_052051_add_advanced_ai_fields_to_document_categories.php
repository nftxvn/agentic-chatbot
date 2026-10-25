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
        Schema::table('document_categories', function (Blueprint $table) {
            $table->string('vision_model')->nullable()->after('ui_layout');
            $table->string('llm_model')->nullable()->after('vision_model');
            $table->decimal('temperature', 3, 2)->default(0.0)->after('llm_model');
            $table->integer('chunk_size')->default(1000)->after('temperature');
            $table->integer('chunk_overlap')->default(200)->after('chunk_size');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('document_categories', function (Blueprint $table) {
            $table->dropColumn([
                'vision_model',
                'llm_model',
                'temperature',
                'chunk_size',
                'chunk_overlap'
            ]);
        });
    }
};
