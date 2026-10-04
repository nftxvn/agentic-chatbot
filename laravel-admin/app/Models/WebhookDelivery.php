<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class WebhookDelivery extends Model
{
    protected $fillable = [
        'event_id',
        'api_key_id',
        'ticket_id',
        'ticket_message_id',
        'event_type',
        'status',
        'attempts',
        'response_status',
        'last_error',
        'delivered_at',
    ];

    protected function casts(): array
    {
        return [
            'attempts' => 'integer',
            'response_status' => 'integer',
            'delivered_at' => 'datetime',
        ];
    }

    public function apiKey(): BelongsTo
    {
        return $this->belongsTo(ApiKey::class);
    }

    public function ticket(): BelongsTo
    {
        return $this->belongsTo(ChatTicket::class);
    }

    public function ticketMessage(): BelongsTo
    {
        return $this->belongsTo(ChatTicketMessage::class, 'ticket_message_id');
    }
}
