<?php

namespace App\Services\Documents;

use App\Models\Document;
use App\Models\EkstraksiHalaman;
use App\Models\EkstraksiJob;
use App\Models\User;
use App\Services\AiMicroserviceClient;
use Illuminate\Support\Facades\DB;

class DocumentExtractionService
{
    public function __construct(
        private AiMicroserviceClient $client,
        private DocumentCategoryOptions $categoryOptions,
    ) {
    }

    public function start(Document $document, ?int $maxPages, ?User $actor): array
    {
        $result = $this->client->mulaiEkstraksi($document->id, $maxPages, $this->categoryOptions->forDocument($document));
        if ($result['success']) {
            $document->update(['status' => 'processing', 'error_message' => null]);
            $document->recordLog('processing', 'Ekstraksi bertahap dimulai oleh ' . ($actor?->name ?? 'Admin'), 15);
        }

        return $result;
    }

    /** @return array{already_requested: bool, data: mixed} */
    public function pause(Document $document, ?User $actor): array
    {
        $job = EkstraksiJob::where('document_id', $document->id)->first();
        $fallback = ['document_id' => $document->id, 'jeda_diminta' => true];
        if ($job && ($job->status === 'jeda' || $job->jeda_diminta)) {
            return ['already_requested' => true, 'data' => $fallback];
        }

        EkstraksiJob::where('document_id', $document->id)->update(['jeda_diminta' => true]);
        $result = $this->client->jedaEkstraksi($document->id);
        $document->recordLog('paused', 'Ekstraksi dokumen dijeda oleh ' . ($actor?->name ?? 'Admin'), 15);

        return ['already_requested' => false, 'data' => $result['data'] ?? $fallback];
    }

    public function status(Document $document): mixed
    {
        $result = $this->client->statusEkstraksi($document->id);
        if ($result['success'] && !empty($result['data'])) {
            return $result['data'];
        }

        $job = EkstraksiJob::where('document_id', $document->id)->first();
        if (!$job) {
            return [
                'document_id' => $document->id,
                'status' => 'antre',
                'jeda_diminta' => false,
                'halaman_total' => $document->total_pages ?? 0,
                'halaman_selesai' => 0,
                'persen' => 0,
                'pesan' => null,
            ];
        }

        $total = (int) ($document->total_pages ?: ($job->halaman_total != 100 ? $job->halaman_total : 0));
        $done = (int) ($job->halaman_total != 100 ? $job->halaman_selesai : ($document->processed_pages ?? 0));
        if ($total > 0 && $done > $total) {
            $done = $total;
        }

        return [
            'document_id' => $document->id,
            'status' => $job->status,
            'jeda_diminta' => (bool) $job->jeda_diminta,
            'halaman_total' => $total,
            'halaman_selesai' => $done,
            'persen' => $total > 0 ? min(100, (int) round(($done / $total) * 100)) : 0,
            'pesan' => $job->pesan,
        ];
    }

    public function pages(Document $document, bool $uncheckedOnly): mixed
    {
        $result = $this->client->daftarHalaman($document->id, $uncheckedOnly);
        if ($result['success']) {
            return $result['data'];
        }

        $query = EkstraksiHalaman::where('document_id', $document->id)->orderBy('page_number');
        if ($uncheckedOnly) {
            $query->where('diperiksa', false);
        }
        $pages = $query->get(['page_number', 'text', 'diperiksa']);

        return ['document_id' => $document->id, 'jumlah' => $pages->count(), 'halaman' => $pages];
    }

    public function saveCorrection(Document $document, int $pageNumber, string $text): array
    {
        $result = $this->client->simpanKoreksiHalaman($document->id, $pageNumber, $text);
        if ($result['success']) {
            DB::table('ekstraksi_halaman')->upsert(
                [[
                    'document_id' => $document->id,
                    'page_number' => $pageNumber,
                    'text' => $text,
                    'diperiksa' => 1,
                ]],
                ['document_id', 'page_number'],
                ['text', 'diperiksa'],
            );
        }

        return $result;
    }

    public function embed(Document $document, array $options, ?User $actor): array
    {
        $result = $this->client->simpanKeKorpus($document->id, $options);
        if ($result['success']) {
            $document->recordLog('completed', 'Dokumen difinalisasi dan disimpan ke korpus vektor oleh ' . ($actor?->name ?? 'Admin'), 15);
        }

        return $result;
    }
}
