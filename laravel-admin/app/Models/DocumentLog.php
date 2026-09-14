<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class DocumentLog extends Model
{
    const CREATED_AT = 'created_at';
    const UPDATED_AT = null;
    public $timestamps = true;

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
            'uploaded'                              => 'Dokumen Diunggah',
            'processing', 'started'                 => 'Ekstraksi Dimulai',
            'paused', 'jeda'                        => 'Ekstraksi Dijeda',
            'resumed', 'dilanjutkan'                => 'Ekstraksi Dilanjutkan',
            'correction_saved', 'koreksi_disimpan'  => 'Koreksi Manual Disimpan',
            'ocr_completed'                         => 'Ekstraksi OCR Selesai',
            'chunked', 'chunking_completed'         => 'Pemotongan Teks (Chunking)',
            'embedding_completed', 'indexed'        => 'Embedding Vektor Disimpan',
            'completed', 'selesai'                  => 'Dokumen Berhasil Diindeks',
            'failed', 'gagal'                       => 'Ekstraksi Gagal',
            'replaced', 'diganti'                   => 'File Dokumen Diganti',
            'cancelled', 'dibatalkan'               => 'Ekstraksi Dibatalkan',
            'ocr_started'                           => 'OCR Dimulai',
            'embedding_started'                     => 'Embedding Dimulai',
            default                                 => ucfirst(str_replace('_', ' ', $this->action)),
        };
    }

    /**
     * Get the action badge color.
     */
    public function getActionColorAttribute(): string
    {
        return match ($this->action) {
            'uploaded'                              => 'sky',
            'processing', 'started'                 => 'amber',
            'paused', 'jeda'                        => 'orange',
            'resumed', 'dilanjutkan'                => 'cyan',
            'correction_saved', 'koreksi_disimpan'  => 'violet',
            'ocr_completed'                         => 'teal',
            'chunked', 'chunking_completed'         => 'indigo',
            'embedding_completed', 'indexed'        => 'sky',
            'completed', 'selesai'                  => 'emerald',
            'failed', 'gagal'                       => 'red',
            'replaced', 'diganti'                   => 'amber',
            'cancelled', 'dibatalkan'               => 'rose',
            'ocr_started'                           => 'purple',
            'embedding_started'                     => 'indigo',
            default                                 => 'gray',
        };
    }

    /**
     * Record a new log with debounce protection against duplicates.
     *
     * @param int $documentId
     * @param string $action
     * @param string|null $details
     * @param int $debounceSeconds Window in seconds to suppress duplicate consecutive logs.
     * @return self
     */
    public static function record(int $documentId, string $action, ?string $details = null, int $debounceSeconds = 15): self
    {
        $latest = self::where('document_id', $documentId)
            ->latest('created_at')
            ->first();

        // If the most recent log has the same action and is within the debounce window
        if ($latest && $latest->action === $action) {
            $secondsDiff = $latest->created_at ? $latest->created_at->diffInSeconds(now()) : 999;
            if ($secondsDiff < $debounceSeconds) {
                // Update details if new details are provided and different
                if ($details && $latest->details !== $details) {
                    $latest->update(['details' => $details]);
                }
                return $latest;
            }
        }

        return self::create([
            'document_id' => $documentId,
            'action'      => $action,
            'details'     => $details,
        ]);
    }
}
