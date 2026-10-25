<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class ChatbotFastPath extends Model
{
    use HasFactory;

    protected $table = 'chatbot_fast_paths';

    protected $fillable = [
        'category',
        'title',
        'keywords',
        'response_text',
        'is_active',
        'sort_order',
    ];

    protected $casts = [
        'is_active'   => 'boolean',
        'sort_order'  => 'integer',
    ];
}
