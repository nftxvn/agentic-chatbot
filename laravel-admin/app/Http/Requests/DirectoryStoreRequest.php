<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class DirectoryStoreRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'nama_bidang'     => 'required|string|max:150',
            'keywords'        => 'required|string',
            'lokasi'          => 'required|string|max:255',
            'email'           => 'required|string|email|max:100',
            'layanan_utama'   => 'required|string|max:150',
            'daftar_tugas'    => 'nullable',
            'jam_operasional' => 'nullable|string|max:100',
            'is_active'       => 'boolean',
            'sort_order'      => 'integer',
        ];
    }
}
