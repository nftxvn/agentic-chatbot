<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\Settings\ChatbotSettingsService;

class SettingController extends Controller
{
    /** Keep the existing default-prompt entrypoint for PHP callers. */
    public static function getDefaultRagPrompt(): string
    {
        return ChatbotSettingsService::getDefaultRagPrompt();
    }
}
