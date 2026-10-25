<?php

namespace App\Http\Requests;

use App\Models\ChatbotDirectory;
use Illuminate\Foundation\Http\FormRequest;

class DirectoryUpdateRequest extends FormRequest
{
    protected function prepareForValidation(): void
    {
        // Preserve the controller's original 404-before-payload-validation order.
        ChatbotDirectory::findOrFail($this->route('id'));
    }

    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'nama_bidang'     => 'sometimes|required|string|max:150',
            'keywords'        => 'sometimes|required|string',
            'lokasi'          => 'sometimes|required|string|max:255',
            'email'           => 'sometimes|required|string|email|max:100',
            'layanan_utama'   => 'sometimes|required|string|max:150',
            'daftar_tugas'    => 'nullable',
            'jam_operasional' => 'nullable|string|max:100',
            'is_active'       => 'boolean',
            'sort_order'      => 'integer',
        ];
    }
}
