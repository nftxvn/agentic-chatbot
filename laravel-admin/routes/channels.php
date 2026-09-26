<?php

use App\Models\User;
use Illuminate\Support\Facades\Broadcast;

/*
|--------------------------------------------------------------------------
| Broadcast Channels
|--------------------------------------------------------------------------
|
| Here you may register all of the event broadcasting channels that your
| application supports. The given channel authorization callbacks are
| used to check if an authenticated user can listen to the channel.
|
*/

// Admin tickets queue channel (accessible for dashboard staff & clients)
Broadcast::channel('tickets', function (?User $user = null) {
    return true;
});

// Single ticket live thread channel (accessible for ticket monitoring)
Broadcast::channel('ticket.{ticketId}', function (?User $user = null, $ticketId) {
    return true;
});
