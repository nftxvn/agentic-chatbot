<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('documents', function (Blueprint $table) {
            $table->integer('processed_pages')->default(0)->after('total_pages');
        });
        
        // Modifikasi ENUM status untuk mendukung cicil (paused) dan pembatalan (cancelled)
        if (DB::getDriverName() === 'mysql') {
            DB::statement("ALTER TABLE documents MODIFY COLUMN status ENUM('pending', 'processing', 'completed', 'failed', 'paused', 'cancelled') DEFAULT 'pending'");
        }
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('documents', function (Blueprint $table) {
            $table->dropColumn('processed_pages');
        });
        
        // Kembalikan ke ENUM awal
        if (DB::getDriverName() === 'mysql') {
            DB::statement("ALTER TABLE documents MODIFY COLUMN status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending'");
        }
    }
};
