<?php

namespace App\Services\Documents;

use App\Models\Document;

class DocumentPresenter
{
    /**
     * Determine the unified effective status and label for a document.
     */
    public function resolveEffectiveStatus(Document $document, int $donePages = 0, int $totalPages = 0): array
    {
        $job    = $document->ekstraksiJob;
        $status = $document->status;

        // 1. Selesai (Completed / Indexed to corpus)
        if ($job?->status === 'selesai' || $status === 'completed') {
            return ['status' => 'completed', 'label' => 'Selesai'];
        }

        // 2. Menunggu Verifikasi (All pages extracted, waiting for human admin review)
        if ($job?->status === 'menunggu_koreksi' || $status === 'menunggu_koreksi' || ($totalPages > 0 && $donePages >= $totalPages && $job?->status !== 'gagal')) {
            return ['status' => 'menunggu_koreksi', 'label' => 'Menunggu Verifikasi'];
        }

        // 3. Sedang Berjalan / Antre (Processing) - Prioritaskan agar background worker aktif langsung tercermin di UI
        if ($job?->status === 'berjalan' || $job?->status === 'ekstraksi' || $job?->status === 'antre' || $status === 'processing') {
            if ($job?->jeda_diminta) {
                return ['status' => 'processing', 'label' => 'Menjeda...'];
            }
            return ['status' => 'processing', 'label' => 'Memproses'];
        }

        // 4. Dijeda (Paused)
        if ($job?->status === 'jeda' || $status === 'paused') {
            return ['status' => 'jeda', 'label' => 'Dijeda'];
        }

        // 5. Gagal (Failed)
        if ($job?->status === 'gagal' || $status === 'failed') {
            return ['status' => 'failed', 'label' => 'Gagal'];
        }

        return [
            'status' => $status ?? 'pending',
            'label'  => $document->status_badge['label'] ?? 'Menunggu',
        ];
    }

    /**
     * Format a document model for API response.
     */
    public function format(Document $document, bool $withLogs = false, array $vectorCounts = []): array
    {
        $job = $document->ekstraksiJob;

        $savedCount  = $document->relationLoaded('ekstraksiHalaman') ? $document->ekstraksiHalaman->count() : $document->ekstraksiHalaman()->count();
        $realTotal   = (int) ($document->total_pages ?: ($job?->halaman_total && $job->halaman_total != 100 ? $job->halaman_total : $savedCount));
        $rawDone     = max($savedCount, (int) ($document->processed_pages ?? 0), ($job && $job->halaman_total != 100 ? (int) $job->halaman_selesai : 0));
        $donePages   = $realTotal > 0 ? min($realTotal, $rawDone) : $rawDone;
        $totalPages  = $realTotal > 0 ? $realTotal : $donePages;
        $percent     = ($totalPages > 0) ? min(100, (int) round(($donePages / $totalPages) * 100)) : 0;

        $resolved    = $this->resolveEffectiveStatus($document, $donePages, $totalPages);
        $status      = $resolved['status'];
        $statusLabel = $resolved['label'];

        // Sinkronisasi jumlah vektor aktif ChromaDB
        $actualVectors = null;
        if (!empty($vectorCounts) && array_key_exists($document->id, $vectorCounts)) {
            $actualVectors = (int) $vectorCounts[$document->id];
        }

        $effectiveChunks = $actualVectors !== null
            ? $actualVectors
            : ($status === 'completed' ? (int) ($document->total_chunks ?? 0) : null);

        // Jika dokumen completed dan jumlah chunk di DB belum sinkron dengan ChromaDB, update diam-diam
        if ($actualVectors !== null && $document->total_chunks !== $actualVectors && $status === 'completed') {
            try {
                $document->updateQuietly(['total_chunks' => $actualVectors]);
            } catch (\Throwable $e) {
                // Ignore silent update errors
            }
        }

        $data = [
            'id'                => $document->id,
            'title'             => $document->title,
            'original_filename' => $document->original_name ?? $document->original_filename,
            'original_name'     => $document->original_name ?? $document->original_filename,
            'file_path'         => $document->file_path,
            'status'            => $status,
            'status_label'      => $statusLabel,
            'pdf_type'          => $document->pdf_type,
            'pdf_type_label'    => $document->pdf_type_label,
            'category_id'       => $document->category_id,
            'category_name'     => $document->category?->name ?? 'Umum',
            'category_ui_layout'=> $document->category?->ui_layout ?? 'general',
            'total_pages'       => $totalPages,
            'processed_pages'   => $donePages,
            'total_chunks'      => $effectiveChunks,
            'vector_count'      => $effectiveChunks,
            'error_message'     => $document->error_message,
            'uploaded_by'       => $document->uploader?->name,
            'pdf_url'           => url("/api/documents/{$document->id}/pdf"),
            'created_at'        => $document->created_at ? \Carbon\Carbon::parse($document->created_at)->toIso8601String() : null,
            'updated_at'        => $document->updated_at ? \Carbon\Carbon::parse($document->updated_at)->toIso8601String() : null,
            'processed_at'      => $document->processed_at ? \Carbon\Carbon::parse($document->processed_at)->toIso8601String() : null,

            // Staged extraction progress
            'ekstraksi_status'  => $job?->status,
            'jeda_diminta'      => (bool) $job?->jeda_diminta,
            'halaman_selesai'   => $donePages,
            'persen_ekstraksi'  => $percent,
        ];

        if ($withLogs) {
            $data['logs'] = $document->logs->map(fn ($log) => [
                'id'          => $log->id,
                'action'      => $log->action,
                'action_label'=> $log->action_label,
                'action_color'=> $log->action_color,
                'details'     => $log->details,
                'created_at'  => $log->created_at ? \Carbon\Carbon::parse($log->created_at)->toIso8601String() : null,
            ])->values();
        }

        return $data;
    }

}
