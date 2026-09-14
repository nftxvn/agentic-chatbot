<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Str;

class ApiKey extends Model
{
    use HasFactory;

    protected $fillable = [
        'name',
        'key',
        'is_active',
        'last_used_at',
    ];

    protected $casts = [
        'is_active' => 'boolean',
        'last_used_at' => 'datetime',
    ];

    /**
     * Generate a secure random API key prefixed with sk_live_
     */
    public static function generateSecretKey(): string
    {
        return 'sk_live_' . Str::random(32);
    }

    /**
     * Get masked representation of key (e.g. sk_live_••••••••••••abcd)
     */
    public function getMaskedKeyAttribute(): string
    {
        if (strlen($this->key) <= 12) {
            return '••••••••••••';
        }
        $prefix = substr($this->key, 0, 8);
        $suffix = substr($this->key, -4);
        return $prefix . '••••••••••••' . $suffix;
    }
}
