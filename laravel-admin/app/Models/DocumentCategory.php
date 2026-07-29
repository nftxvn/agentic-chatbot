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
        'llm_prompt',
        'prompt_variables',
        'ui_layout',
        'vision_model',
        'llm_model',
        'temperature',
        'chunk_size',
        'chunk_overlap',
        'is_active',
    ];

    protected $casts = [
        'prompt_variables' => 'array',
        'is_active' => 'boolean',
        'temperature' => 'float',
        'chunk_size' => 'integer',
        'chunk_overlap' => 'integer',
    ];
}
