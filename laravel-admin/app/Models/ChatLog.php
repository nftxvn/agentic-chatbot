<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class ChatLog extends Model
{
    use HasFactory;

    protected $fillable = [
        'session_id',
        'channel',
        'api_key_id',
        'sender_identifier',
        'query',
        'answer',
        'sources_json',
        'is_fallback',
        'response_time_ms',
    ];

    protected $casts = [
        'sources_json' => 'array',
        'is_fallback' => 'boolean',
        'response_time_ms' => 'integer',
    ];

    public function apiKey()
    {
        return $this->belongsTo(ApiKey::class);
    }
}
