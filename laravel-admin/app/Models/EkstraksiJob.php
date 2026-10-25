<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class EkstraksiJob extends Model
{
    protected $table = 'ekstraksi_job';
    protected $primaryKey = 'document_id';
    public $incrementing = false;
    public $timestamps = false;

    protected $fillable = [
        'document_id',
        'status',
        'jeda_diminta',
        'halaman_total',
        'halaman_selesai',
        'petunjuk_format',
        'pesan',
    ];

    protected function casts(): array
    {
        return [
            'jeda_diminta' => 'boolean',
            'halaman_total' => 'integer',
            'halaman_selesai' => 'integer',
            'updated_at' => 'datetime',
        ];
    }

    public function document(): BelongsTo
    {
        return $this->belongsTo(Document::class, 'document_id');
    }

    /**
     * Helper to compute progress percentage.
     */
    public function getPersenAttribute(): int
    {
        if (!$this->halaman_total || $this->halaman_total <= 0) {
            return 0;
        }

        return (int) min(100, round(($this->halaman_selesai / $this->halaman_total) * 100));
    }
}
