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
        Schema::create('chat_tickets', function (Blueprint $table) {
            $table->id();
            $table->string('ticket_number', 50)->unique()->index();
            $table->string('session_id', 100)->index();
            $table->string('citizen_name', 150)->nullable();
            $table->string('citizen_contact', 150)->nullable();
            $table->string('citizen_agency', 150)->nullable();
            $table->string('channel', 50)->default('widget')->index(); // widget, whatsapp, telegram
            $table->string('status', 30)->default('open')->index();    // open, in_progress, resolved, closed
            $table->string('priority', 30)->default('medium')->index();// low, medium, high, urgent
            $table->text('issue_summary')->nullable();
            $table->foreignId('assigned_admin_id')->nullable()->constrained('users')->nullOnDelete();
            $table->json('metadata')->nullable();
            $table->timestamp('last_message_at')->nullable()->index();
            $table->timestamp('resolved_at')->nullable();
            $table->timestamp('closed_at')->nullable();
            $table->timestamps();
        });

        Schema::create('chat_ticket_messages', function (Blueprint $table) {
            $table->id();
            $table->foreignId('ticket_id')->constrained('chat_tickets')->cascadeOnDelete();
            $table->string('sender_type', 30)->default('citizen')->index(); // citizen, agent, bot, system
            $table->foreignId('sender_id')->nullable()->constrained('users')->nullOnDelete();
            $table->string('sender_name', 150);
            $table->text('message');
            $table->json('attachments')->nullable();
            $table->boolean('is_internal_note')->default(false)->index();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('chat_ticket_messages');
        Schema::dropIfExists('chat_tickets');
    }
};
