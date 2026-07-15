<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class AppSetting extends Model
{
    use HasFactory;

    protected $fillable = ['setting_key', 'setting_value'];

    /**
     * Helper to get a setting value easily.
     */
    public static function getVal($key, $default = null)
    {
        $setting = self::where('setting_key', $key)->first();
        return $setting ? $setting->setting_value : $default;
    }

    /**
     * Helper to set a setting value easily.
     */
    public static function setVal($key, $value)
    {
        return self::updateOrCreate(
            ['setting_key' => $key],
            ['setting_value' => $value]
        );
    }
}
