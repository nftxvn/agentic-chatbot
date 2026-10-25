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
        Schema::table('documents', function (Blueprint $table) {
            $table->longText('flowchart_data')->nullable()->after('status');
            $table->string('flowchart_status')->default('draft')->after('flowchart_data');
            $table->longText('flowchart_markdown')->nullable()->after('flowchart_status');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('documents', function (Blueprint $table) {
            $table->dropColumn(['flowchart_data', 'flowchart_status', 'flowchart_markdown']);
        });
    }
};
