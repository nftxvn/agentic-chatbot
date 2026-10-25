<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ChatTicketMessage extends Model
{
    use HasFactory;

    protected $table = 'chat_ticket_messages';

    protected $fillable = [
        'ticket_id',
        'sender_type',
        'sender_id',
        'sender_name',
        'message',
        'attachments',
        'is_internal_note',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'attachments' => 'array',
            'is_internal_note' => 'boolean',
        ];
    }

    /**
     * Parent ticket.
     */
    public function ticket(): BelongsTo
    {
        return $this->belongsTo(ChatTicket::class, 'ticket_id');
    }

    /**
     * Sender staff user (if agent or system user).
     */
    public function sender(): BelongsTo
    {
        return $this->belongsTo(User::class, 'sender_id');
    }
}
