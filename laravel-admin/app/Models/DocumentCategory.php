<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class DocumentCategory extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'description',
        'vision_prompt',
        'prompt_variables',
        'ui_layout',
        'vision_model',
        'is_active',
    ];

    protected $casts = [
        'prompt_variables' => 'array',
        'is_active' => 'boolean',
    ];
}
