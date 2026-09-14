<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatbotDirectory;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class DirectoryController extends Controller
{
    /**
     * Menampilkan daftar Direktori Bidang & Layanan.
     */
    public function index(Request $request): JsonResponse
    {
        $query = ChatbotDirectory::query();

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('nama_bidang', 'like', "%{$search}%")
                  ->orWhere('keywords', 'like', "%{$search}%")
                  ->orWhere('layanan_utama', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%")
                  ->orWhere('lokasi', 'like', "%{$search}%");
            });
        }

        if ($request->filled('is_active')) {
            $query->where('is_active', filter_var($request->is_active, FILTER_VALIDATE_BOOLEAN));
        }

        $items = $query->orderBy('sort_order', 'asc')
                       ->orderBy('id', 'asc')
                       ->get();

        return response()->json([
            'success' => true,
            'data'    => $items,
            'total'   => $items->count(),
        ]);
    }

    /**
     * Menyimpan Direktori Bidang baru.
     */
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'nama_bidang'     => 'required|string|max:150',
            'keywords'        => 'required|string',
            'lokasi'          => 'required|string|max:255',
            'email'           => 'required|string|email|max:100',
            'layanan_utama'   => 'required|string|max:150',
            'daftar_tugas'    => 'nullable',
            'jam_operasional' => 'nullable|string|max:100',
            'is_active'       => 'boolean',
            'sort_order'      => 'integer',
        ]);

        if (isset($validated['daftar_tugas']) && is_string($validated['daftar_tugas'])) {
            // Konversi teks baris-per-baris menjadi array
            $lines = array_filter(array_map('trim', explode("\n", $validated['daftar_tugas'])));
            $validated['daftar_tugas'] = array_values($lines);
        }

        $item = ChatbotDirectory::create($validated);

        return response()->json([
            'success' => true,
            'message' => 'Direktori Bidang berhasil ditambahkan.',
            'data'    => $item,
        ], 201);
    }

    /**
     * Menampilkan detail satu Direktori.
     */
    public function show(int $id): JsonResponse
    {
        $item = ChatbotDirectory::findOrFail($id);

        return response()->json([
            'success' => true,
            'data'    => $item,
        ]);
    }

    /**
     * Memperbarui Direktori Bidang.
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $item = ChatbotDirectory::findOrFail($id);

        $validated = $request->validate([
            'nama_bidang'     => 'sometimes|required|string|max:150',
            'keywords'        => 'sometimes|required|string',
            'lokasi'          => 'sometimes|required|string|max:255',
            'email'           => 'sometimes|required|string|email|max:100',
            'layanan_utama'   => 'sometimes|required|string|max:150',
            'daftar_tugas'    => 'nullable',
            'jam_operasional' => 'nullable|string|max:100',
            'is_active'       => 'boolean',
            'sort_order'      => 'integer',
        ]);

        if (isset($validated['daftar_tugas']) && is_string($validated['daftar_tugas'])) {
            $lines = array_filter(array_map('trim', explode("\n", $validated['daftar_tugas'])));
            $validated['daftar_tugas'] = array_values($lines);
        }

        $item->update($validated);

        return response()->json([
            'success' => true,
            'message' => 'Direktori Bidang berhasil diperbarui.',
            'data'    => $item,
        ]);
    }

    /**
     * Toggle status aktif / nonaktif.
     */
    public function toggle(int $id): JsonResponse
    {
        $item = ChatbotDirectory::findOrFail($id);
        $item->is_active = !$item->is_active;
        $item->save();

        return response()->json([
            'success' => true,
            'message' => 'Status Direktori berhasil diubah.',
            'data'    => $item,
        ]);
    }

    /**
     * Menghapus Direktori Bidang.
     */
    public function destroy(int $id): JsonResponse
    {
        $item = ChatbotDirectory::findOrFail($id);
        $item->delete();

        return response()->json([
            'success' => true,
            'message' => 'Direktori Bidang berhasil dihapus.',
        ]);
    }
}
