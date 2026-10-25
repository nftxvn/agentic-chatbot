<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('api_keys', function (Blueprint $table) {
            $table->text('webhook_url')->nullable();
            $table->text('webhook_secret')->nullable();
            $table->boolean('webhook_enabled')->default(false);
        });

        Schema::table('chat_tickets', function (Blueprint $table) {
            $table->foreignId('api_key_id')->nullable()->after('session_id')
                ->constrained('api_keys')->nullOnDelete();
        });

        Schema::create('webhook_deliveries', function (Blueprint $table) {
            $table->id();
            $table->uuid('event_id')->unique();
            $table->foreignId('api_key_id')->nullable()->constrained('api_keys')->nullOnDelete();
            $table->foreignId('ticket_id')->nullable()->constrained('chat_tickets')->nullOnDelete();
            $table->foreignId('ticket_message_id')->nullable()->constrained('chat_ticket_messages')->nullOnDelete();
            $table->string('event_type', 100);
            $table->string('status', 20)->default('queued')->index();
            $table->unsignedTinyInteger('attempts')->default(0);
            $table->unsignedSmallInteger('response_status')->nullable();
            $table->text('last_error')->nullable();
            $table->timestamp('delivered_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('webhook_deliveries');

        Schema::table('chat_tickets', function (Blueprint $table) {
            $table->dropConstrainedForeignId('api_key_id');
        });

        Schema::table('api_keys', function (Blueprint $table) {
            $table->dropColumn(['webhook_url', 'webhook_secret', 'webhook_enabled']);
        });
    }
};
