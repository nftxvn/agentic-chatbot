<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class ChatbotDirectory extends Model
{
    use HasFactory;

    protected $table = 'chatbot_directories';

    protected $fillable = [
        'nama_bidang',
        'keywords',
        'lokasi',
        'email',
        'layanan_utama',
        'daftar_tugas',
        'jam_operasional',
        'is_active',
        'sort_order',
    ];

    protected $casts = [
        'daftar_tugas' => 'array',
        'is_active'    => 'boolean',
        'sort_order'   => 'integer',
    ];
}
