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
        Schema::create('document_categories', function (Blueprint $table) {
            $table->id();
            $table->string('name')->unique();
            $table->text('description')->nullable();
            
            // Dynamic Prompts
            $table->longText('vision_prompt')->nullable();
            $table->longText('llm_prompt')->nullable();
            
            // Any specific JSON variables or lists (like Job Titles, Rules) that need to be injected into the prompt
            $table->json('prompt_variables')->nullable();
            
            // Tells the frontend what UI to render for this document (e.g. 'general', 'flowchart')
            $table->string('ui_layout')->default('general');
            
            $table->boolean('is_active')->default(true);
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('document_categories');
    }
};
