<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Artisan::command('tickets:prune-attachments {--days=30 : Jumlah hari retensi file tiket yang sudah ditutup}', function () {
    $days = (int) $this->option('days');
    $cutoff = now()->subDays($days);

    $closedTickets = \App\Models\ChatTicket::whereIn('status', ['closed', 'resolved'])
        ->where(function ($q) use ($cutoff) {
            $q->where('closed_at', '<', $cutoff)
              ->orWhere(function ($sub) use ($cutoff) {
                  $sub->whereNull('closed_at')->where('resolved_at', '<', $cutoff);
              });
        })
        ->get();

    $prunedCount = 0;
    foreach ($closedTickets as $ticket) {
        $dir = "private/tickets/{$ticket->id}";
        if (\Illuminate\Support\Facades\Storage::disk('local')->exists($dir)) {
            \Illuminate\Support\Facades\Storage::disk('local')->deleteDirectory($dir);
            $prunedCount++;
        }
    }

    $this->info("Berhasil membersihkan {$prunedCount} direktori lampiran tiket yang telah ditutup lebih dari {$days} hari.");
})->purpose('Membersihkan file fisik lampiran tiket lama untuk menjaga kapasitas disk server');

Artisan::command('documents:sync-vectors', function () {
    $aiClient = new \App\Services\AiMicroserviceClient();
    $counts = $aiClient->getVectorCounts();

    $this->info("Menghubungi ChromaDB via AI microservice...");
    if (empty($counts)) {
        $this->warn("Tidak ada data vektor yang ditemukan atau koneksi ke AI service gagal.");
        return;
    }

    $updated = 0;
    foreach ($counts as $docId => $count) {
        $doc = \App\Models\Document::find($docId);
        if ($doc) {
            $doc->updateQuietly(['total_chunks' => (int) $count]);
            $this->line("Dokumen #{$docId} ({$doc->title}): {$count} vektor sinkron.");
            $updated++;
        }
    }

    $this->info("Sinkronisasi selesai. {$updated} dokumen berhasil diperbarui sesuai ChromaDB.");
})->purpose('Sinkronisasi jumlah vektor aktif dokumen di MySQL dengan ChromaDB');

\Illuminate\Support\Facades\Schedule::command('documents:sync-vectors')->hourly();


