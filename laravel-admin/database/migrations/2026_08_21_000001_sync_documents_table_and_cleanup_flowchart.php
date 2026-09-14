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
            // Drop obsolete flowchart columns
            if (Schema::hasColumn('documents', 'flowchart_data')) {
                $table->dropColumn(['flowchart_data', 'flowchart_status', 'flowchart_markdown']);
            }

            // Rename columns to match Python-AI database queries exactly
            if (Schema::hasColumn('documents', 'original_filename') && !Schema::hasColumn('documents', 'original_name')) {
                $table->renameColumn('original_filename', 'original_name');
            }

            if (Schema::hasColumn('documents', 'storage_path') && !Schema::hasColumn('documents', 'file_path')) {
                $table->renameColumn('storage_path', 'file_path');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('documents', function (Blueprint $table) {
            if (Schema::hasColumn('documents', 'original_name') && !Schema::hasColumn('documents', 'original_filename')) {
                $table->renameColumn('original_name', 'original_filename');
            }

            if (Schema::hasColumn('documents', 'file_path') && !Schema::hasColumn('documents', 'storage_path')) {
                $table->renameColumn('file_path', 'storage_path');
            }

            $table->longText('flowchart_data')->nullable()->after('status');
            $table->string('flowchart_status')->default('draft')->after('flowchart_data');
            $table->longText('flowchart_markdown')->nullable()->after('flowchart_status');
        });
    }
};
