<?php

namespace App\Services;

use App\Services\Entities\NormalizesCitizenEntities;
use App\Services\Entities\ParsesCitizenEntities;
use App\Services\Entities\ReadsSessionEntities;
use App\Services\Entities\EnrichesTicketEntities;

/**
 * API statis kompatibel untuk ekstraksi identitas warga dan enrichment tiket.
 *
 * Implementasi dibagi menurut parsing, normalisasi, riwayat, dan penerapan data.
 */
class EntityExtractorService
{
    use NormalizesCitizenEntities;
    use ParsesCitizenEntities;
    use ReadsSessionEntities;
    use EnrichesTicketEntities;
}
