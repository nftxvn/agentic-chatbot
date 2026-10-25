<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class EkstraksiHalaman extends Model
{
    protected $table = 'ekstraksi_halaman';
    public $incrementing = false;
    public $timestamps = false;

    protected $fillable = [
        'document_id',
        'page_number',
        'text',
        'diperiksa',
        'created_at',
    ];

    protected function casts(): array
    {
        return [
            'document_id' => 'integer',
            'page_number' => 'integer',
            'diperiksa' => 'boolean',
            'created_at' => 'datetime',
        ];
    }

    public function document(): BelongsTo
    {
        return $this->belongsTo(Document::class, 'document_id');
    }

    /**
     * Set the keys for a save update query (Composite Primary Key).
     */
    protected function setKeysForSaveQuery($query)
    {
        return $query->where('document_id', $this->getAttribute('document_id'))
                     ->where('page_number', $this->getAttribute('page_number'));
    }
}
