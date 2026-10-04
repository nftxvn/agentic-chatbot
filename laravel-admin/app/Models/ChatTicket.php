<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Carbon;

class ChatTicket extends Model
{
    use HasFactory;

    protected $table = 'chat_tickets';

    protected $fillable = [
        'ticket_number',
        'session_id',
        'api_key_id',
        'citizen_name',
        'citizen_contact',
        'citizen_agency',
        'channel',
        'status',
        'priority',
        'issue_summary',
        'assigned_admin_id',
        'metadata',
        'last_message_at',
        'resolved_at',
        'closed_at',
    ];

    protected $appends = [
        'unread_messages_count',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'metadata' => 'array',
            'last_message_at' => 'datetime',
            'resolved_at' => 'datetime',
            'closed_at' => 'datetime',
        ];
    }

    protected static function booted(): void
    {
        static::creating(function (ChatTicket $ticket) {
            if (empty($ticket->ticket_number)) {
                $ticket->ticket_number = static::generateTicketNumber();
            }
            if (empty($ticket->last_message_at)) {
                $ticket->last_message_at = now();
            }
        });
    }

    /**
     * Auto-generate a unique ticket number formatted as TICK-DDMMYY-NNN.
     * Example: TICK-270926-001
     */
    public static function generateTicketNumber(): string
    {
        $dateCode = date('dmy'); // e.g. 270926 for 27 Sept 2026
        $prefix = "TICK-{$dateCode}-";

        $latest = static::where('ticket_number', 'LIKE', "{$prefix}%")
            ->latest('id')
            ->first();

        $nextSequence = 1;
        if ($latest && preg_match('/TICK-\d{6}-(\d+)/', $latest->ticket_number, $matches)) {
            $nextSequence = ((int) $matches[1]) + 1;
        }

        return sprintf('%s%03d', $prefix, $nextSequence);
    }

    /**
     * Conversation message history.
     */
    public function messages(): HasMany
    {
        return $this->hasMany(ChatTicketMessage::class, 'ticket_id');
    }

    /**
     * Assigned staff user.
     */
    public function assignedAdmin(): BelongsTo
    {
        return $this->belongsTo(User::class, 'assigned_admin_id');
    }

    /**
     * Scope query to open tickets.
     */
    public function scopeOpen($query)
    {
        return $query->where('status', 'open');
    }

    /**
     * Scope query to in-progress tickets.
     */
    public function scopeInProgress($query)
    {
        return $query->where('status', 'in_progress');
    }

    /**
     * Scope query to resolved tickets.
     */
    public function scopeResolved($query)
    {
        return $query->where('status', 'resolved');
    }

    /**
     * Scope query to closed tickets.
     */
    public function scopeClosed($query)
    {
        return $query->where('status', 'closed');
    }

    public function isOpen(): bool
    {
        return $this->status === 'open';
    }

    public function isInProgress(): bool
    {
        return $this->status === 'in_progress';
    }

    public function isResolved(): bool
    {
        return $this->status === 'resolved';
    }

    public function isClosed(): bool
    {
        return $this->status === 'closed';
    }

    /**
     * Count unread citizen messages since the last agent response.
     */
    public function getUnreadMessagesCountAttribute(): int
    {
        if ($this->relationLoaded('messages')) {
            $messages = $this->messages;
            $lastAgentIndex = $messages->filter(fn ($m) => $m->sender_type === 'agent')->keys()->last();
            if ($lastAgentIndex === null) {
                return $messages->where('sender_type', 'citizen')->count();
            }
            return $messages->slice($lastAgentIndex + 1)->where('sender_type', 'citizen')->count();
        }

        $lastAgentMessage = $this->messages()
            ->where('sender_type', 'agent')
            ->latest('id')
            ->first();

        $query = $this->messages()->where('sender_type', 'citizen');
        if ($lastAgentMessage) {
            $query->where('id', '>', $lastAgentMessage->id);
        }

        return $query->count();
    }
}
