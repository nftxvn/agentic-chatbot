<?php

declare(strict_types=1);

use App\Models\ChatTicket;
use App\Models\User;
use Illuminate\Support\Facades\Hash;

// Reuse all disposable-database/storage guards before any fixture mutation.
ob_start();
require __DIR__.'/prepare.php';
ob_end_clean();

$admin = User::firstOrCreate(['email' => 'browser@example.test'], [
    'name' => 'Browser Test Admin',
    'password' => Hash::make('Browser-Synthetic-Only-2026!'),
]);
$tickets = [];
foreach (['Riwayat panjang sintetis', 'Percakapan kedua sintetis'] as $index => $summary) {
    $ticket = ChatTicket::create([
        'session_id' => 'browser-synthetic-'.$index,
        'citizen_name' => 'Pengguna Uji '.($index + 1),
        'citizen_contact' => 'synthetic@example.test',
        'channel' => 'web',
        'status' => 'in_progress',
        'issue_summary' => $summary,
        'assigned_admin_id' => $admin->id,
    ]);
    for ($number = 1; $number <= ($index === 0 ? 35 : 3); $number++) {
        $message = $ticket->messages()->create([
            'sender_type' => $number % 2 ? 'citizen' : 'agent',
            'sender_id' => $number % 2 ? null : $admin->id,
            'sender_name' => $number % 2 ? $ticket->citizen_name : $admin->name,
            'message' => "Pesan sintetis {$number}: pemeriksaan fokus dan scroll browser. Tidak ada data warga atau pengiriman kanal eksternal dalam fixture ini.",
            'is_internal_note' => false,
        ]);
        $message->forceFill(['created_at' => now()->subMinutes(40 - $number)])->save();
    }
    $tickets[] = $ticket->id;
}
echo json_encode(['admin_id' => $admin->id, 'ticket_ids' => $tickets], JSON_THROW_ON_ERROR).PHP_EOL;
