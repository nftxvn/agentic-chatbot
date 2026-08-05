<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Document extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'title',
        'original_filename',
        'storage_path',
        'status',
        'flowchart_data',
        'flowchart_status',
        'flowchart_markdown',
        'pdf_type',
        'category_id',
        'error_message',
        'total_pages',
        'total_chunks',
        'uploaded_by',
        'processed_at',
    ];

    /**
     * The attributes that should be cast.
     */
    protected function casts(): array
    {
        return [
            'processed_at' => 'datetime',
            'total_pages' => 'integer',
            'total_chunks' => 'integer',
            'flowchart_data' => 'array',
        ];
    }

    /**
     * Get the user who uploaded the document.
     */
    public function uploader(): BelongsTo
    {
        return $this->belongsTo(User::class, 'uploaded_by');
    }

    /**
     * Get the category associated with the document.
     */
    public function category(): BelongsTo
    {
        return $this->belongsTo(DocumentCategory::class, 'category_id');
    }

    /**
     * Get the processing logs for the document.
     */
    public function logs(): HasMany
    {
        return $this->hasMany(DocumentLog::class)->orderBy('created_at', 'desc');
    }

    /**
     * Get the status badge color for display.
     */
    public function getStatusBadgeAttribute(): array
    {
        return match ($this->status) {
            'pending' => [
                'color' => 'gray',
                'bg' => 'bg-gray-100 dark:bg-gray-700',
                'text' => 'text-gray-800 dark:text-gray-300',
                'label' => 'Menunggu',
            ],
            'processing' => [
                'color' => 'yellow',
                'bg' => 'bg-yellow-100 dark:bg-yellow-900/30',
                'text' => 'text-yellow-800 dark:text-yellow-300',
                'label' => 'Memproses',
            ],
            'completed' => [
                'color' => 'green',
                'bg' => 'bg-green-100 dark:bg-green-900/30',
                'text' => 'text-green-800 dark:text-green-300',
                'label' => 'Selesai',
            ],
            'failed' => [
                'color' => 'red',
                'bg' => 'bg-red-100 dark:bg-red-900/30',
                'text' => 'text-red-800 dark:text-red-300',
                'label' => 'Gagal',
            ],
            default => [
                'color' => 'gray',
                'bg' => 'bg-gray-100 dark:bg-gray-700',
                'text' => 'text-gray-800 dark:text-gray-300',
                'label' => 'Tidak Diketahui',
            ],
        };
    }

    /**
     * Get the PDF type label in Indonesian.
     */
    public function getPdfTypeLabelAttribute(): string
    {
        return match ($this->pdf_type) {
            'text' => 'Teks',
            'scanned' => 'Scan/Gambar',
            'mixed' => 'Campuran',
            default => 'Belum Diketahui',
        };
    }
}
