<?php

namespace App\Services\Channels;

final readonly class ChannelResponse
{
    public function __construct(public array $payload, public int $status = 200)
    {
    }
}
