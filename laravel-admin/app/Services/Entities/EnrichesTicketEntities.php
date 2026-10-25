<?php

namespace App\Services\Entities;

use App\Models\ChatTicket;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

/**
 * Penerapan identitas/ringkasan baru serta pembaruan nama pesan warga.
 *
 * Trait dimuat pada EntityExtractorService untuk mempertahankan binding self::
 * serta properti/helper protected tanpa menyalin state atau algoritme.
 *
 * @mixin \App\Services\EntityExtractorService
 */
trait EnrichesTicketEntities
{
    /**
     * Memperkaya (auto-enrich) tiket yang sedang berjalan secara dinamis
     * jika warga memberikan informasi identitas/kendala baru di tengah percakapan.
     */
    public static function enrichTicket(ChatTicket $ticket, string $incomingText, ?string $senderName = null): bool
    {
        $entities = self::extractFromText($incomingText, $senderName);
        $updated = false;

        $hasIntroductionOrName = (bool) preg_match('/(?:nama(?:\s*(?:saya|ku))?|namaku|atas\s+nama|panggil\s+saja|perkenalkan|name)/i', $incomingText)
            || (bool) preg_match('/(?:saya|dengan|aku)\s+[A-Za-z\s\'\.]{2,30}?\s+(?:dari|staf|pegawai|kantor|opd|instansi|dinas)/i', $incomingText);
        $hasExplicitIssue = (bool) preg_match('/(?:kendala|masalah|keluhan|keperluan|perihal|kebutuhan)\s*[:=]/i', $incomingText);

        // 1. Perbarui Nama jika saat ini masih kosong / default / salah ('Warga', 'Bicara', dsb.) atau user memberikan nama baru
        $currentName = trim($ticket->citizen_name ?? '');
        $isGenericName = empty($currentName) || in_array(strtolower($currentName), ['warga', 'warga / anonim', 'warga telegram', 'warga whatsapp', 'user', 'anonim', 'defaultuser', 'bicara', 'admin', 'petugas', 'null']);

        if (!empty($entities['name']) && ($isGenericName || $hasIntroductionOrName)) {
            $ticket->citizen_name = $entities['name'];
            $updated = true;

            // Retroaktif perbarui sender_name pesan warga sebelumnya yang masih 'Warga' atau 'Bicara'
            try {
                $ticket->messages()
                    ->where('sender_type', 'citizen')
                    ->whereIn('sender_name', ['Warga', 'Warga / Anonim', 'Warga Telegram', 'Warga WhatsApp', 'User', 'Bicara', 'Admin'])
                    ->update(['sender_name' => $entities['name']]);
            } catch (\Exception $e) {
                // Ignore
            }
        }

        // 2. Perbarui Instansi jika belum ada atau ada instansi valid yang baru disampaikan
        if (!empty($entities['agency']) && (empty($ticket->citizen_agency) || $entities['agency'] !== $ticket->citizen_agency)) {
            $ticket->citizen_agency = $entities['agency'];
            $updated = true;
        }

        // 3. Perbarui Ringkasan Masalah jika saat ini generic atau user memberikan rincian kendala eksplisit
        $currentIssue = strtolower(trim($ticket->issue_summary ?? ''));
        $isGenericIssue = empty($currentIssue)
            || str_contains($currentIssue, 'hubungi admin')
            || str_contains($currentIssue, 'hubungkan')
            || str_contains($currentIssue, 'permintaan bantuan langsung')
            || str_contains($currentIssue, 'bantuan koordinasi untuk')
            || str_contains($currentIssue, 'assalamualaikum')
            || str_contains($currentIssue, 'halo')
            || str_contains($currentIssue, 'selamat')
            || str_starts_with($currentIssue, 'pertanyaan:');

        if (!empty($entities['issue_summary']) && !self::isPureGreetingOrHandoff($entities['issue_summary']) && ($isGenericIssue || $hasExplicitIssue)) {
            $ticket->issue_summary = Str::limit($entities['issue_summary'], 250);
            $updated = true;
        } elseif ($isGenericIssue && !empty($ticket->citizen_agency) && !empty($ticket->citizen_name)) {
            $ticket->issue_summary = "Bantuan koordinasi untuk {$ticket->citizen_name} ({$ticket->citizen_agency})";
            $updated = true;
        }

        if ($updated) {
            $ticket->save();
            Log::info("ChatTicket #{$ticket->id} berhasil diperkaya dengan entitas baru:", [
                'citizen_name' => $ticket->citizen_name,
                'citizen_agency' => $ticket->citizen_agency,
                'issue_summary' => $ticket->issue_summary,
            ]);
        }

        return $updated;
    }
}
