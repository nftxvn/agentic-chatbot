<?php

namespace App\Services\Documents;

use App\Models\Document;

final readonly class DocumentUploadResult
{
    public function __construct(public Document $document, public bool $aiAvailable)
    {
    }
}
