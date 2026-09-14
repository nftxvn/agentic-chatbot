<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Document extends Model
{
    use HasFactory;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'title',
        'original_name',
        'original_filename', // backward compatibility alias
        'file_path',
        'storage_path',      // backward compatibility alias
        'status',
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
        ];
    }

    /**
     * Backward compatibility accessor for original_filename.
     */
    public function getOriginalFilenameAttribute(): ?string
    {
        return $this->attributes['original_name'] ?? $this->attributes['original_filename'] ?? null;
    }

    /**
     * Backward compatibility mutator for original_filename.
     */
    public function setOriginalFilenameAttribute(?string $value): void
    {
        $this->attributes['original_name'] = $value;
    }

    /**
     * Backward compatibility accessor for storage_path.
     */
    public function getStoragePathAttribute(): ?string
    {
        return $this->attributes['file_path'] ?? $this->attributes['storage_path'] ?? null;
    }

    /**
     * Backward compatibility mutator for storage_path.
     */
    public function setStoragePathAttribute(?string $value): void
    {
        $this->attributes['file_path'] = $value;
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
     * Record an activity log for this document with duplicate protection.
     */
    public function recordLog(string $action, ?string $details = null, int $debounceSeconds = 15): DocumentLog
    {
        return DocumentLog::record($this->id, $action, $details, $debounceSeconds);
    }

    /**
     * Staged extraction job tracking.
     */
    public function ekstraksiJob(): HasOne
    {
        return $this->hasOne(EkstraksiJob::class, 'document_id');
    }

    /**
     * Staged extraction pages.
     */
    public function ekstraksiHalaman(): HasMany
    {
        return $this->hasMany(EkstraksiHalaman::class, 'document_id')->orderBy('page_number');
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
            'processing', 'berjalan', 'antre' => [
                'color' => 'yellow',
                'bg' => 'bg-yellow-100 dark:bg-yellow-900/30',
                'text' => 'text-yellow-800 dark:text-yellow-300',
                'label' => 'Memproses',
            ],
            'completed', 'selesai' => [
                'color' => 'green',
                'bg' => 'bg-green-100 dark:bg-green-900/30',
                'text' => 'text-green-800 dark:text-green-300',
                'label' => 'Selesai',
            ],
            'menunggu_koreksi' => [
                'color' => 'blue',
                'bg' => 'bg-sky-100 dark:bg-sky-900/30',
                'text' => 'text-sky-800 dark:text-sky-300',
                'label' => 'Menunggu Verifikasi',
            ],
            'jeda', 'paused' => [
                'color' => 'orange',
                'bg' => 'bg-orange-100 dark:bg-orange-900/30',
                'text' => 'text-orange-800 dark:text-orange-300',
                'label' => 'Dijeda',
            ],
            'failed', 'gagal' => [
                'color' => 'red',
                'bg' => 'bg-red-100 dark:bg-red-900/30',
                'text' => 'text-red-800 dark:text-red-300',
                'label' => 'Gagal',
            ],
            'cancelled' => [
                'color' => 'gray',
                'bg' => 'bg-gray-200 dark:bg-gray-800',
                'text' => 'text-gray-600 dark:text-gray-400',
                'label' => 'Dibatalkan',
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
