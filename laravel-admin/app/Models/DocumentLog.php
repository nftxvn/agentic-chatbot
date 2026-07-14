<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class DocumentLog extends Model
{
    /**
     * Indicates if the model should be timestamped.
     * We only use created_at, managed by the database.
     */
    public $timestamps = false;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'document_id',
        'action',
        'details',
    ];

    /**
     * Get the document that this log belongs to.
     */
    public function document(): BelongsTo
    {
        return $this->belongsTo(Document::class);
    }

    /**
     * Get the action label in Indonesian.
     */
    public function getActionLabelAttribute(): string
    {
        return match ($this->action) {
            'uploaded' => 'Diunggah',
            'processing' => 'Memproses',
            'ocr_started' => 'OCR Dimulai',
            'embedding_started' => 'Embedding Dimulai',
            'completed' => 'Selesai',
            'failed' => 'Gagal',
            'replaced' => 'Diganti',
            default => $this->action,
        };
    }

    /**
     * Get the action badge color.
     */
    public function getActionColorAttribute(): string
    {
        return match ($this->action) {
            'uploaded' => 'blue',
            'processing' => 'yellow',
            'ocr_started' => 'purple',
            'embedding_started' => 'indigo',
            'completed' => 'green',
            'failed' => 'red',
            'replaced' => 'orange',
            default => 'gray',
        };
    }
}
