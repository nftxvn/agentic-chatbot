<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatbotFastPath;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class FastPathController extends Controller
{
    /**
     * Menampilkan daftar data Fast-Path FAQ.
     */
    public function index(Request $request): JsonResponse
    {
        $query = ChatbotFastPath::query();

        if ($request->filled('category') && $request->category !== 'all') {
            $query->where('category', $request->category);
        }

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('title', 'like', "%{$search}%")
                  ->orWhere('keywords', 'like', "%{$search}%")
                  ->orWhere('response_text', 'like', "%{$search}%");
            });
        }

        if ($request->filled('is_active')) {
            $query->where('is_active', filter_var($request->is_active, FILTER_VALIDATE_BOOLEAN));
        }

        $items = $query->orderBy('sort_order', 'asc')
                       ->orderBy('id', 'desc')
                       ->get();

        return response()->json([
            'success' => true,
            'data'    => $items,
            'total'   => $items->count(),
        ]);
    }

    /**
     * Menyimpan data Fast-Path FAQ baru.
     */
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'category'      => 'required|string|in:general,layanan,sop,faq',
            'title'         => 'required|string|max:150',
            'keywords'      => 'required|string',
            'response_text' => 'required|string',
            'is_active'     => 'boolean',
            'sort_order'    => 'integer',
        ]);

        $item = ChatbotFastPath::create($validated);

        return response()->json([
            'success' => true,
            'message' => 'Fast-Path FAQ berhasil ditambahkan.',
            'data'    => $item,
        ], 201);
    }

    /**
     * Menampilkan detail satu item Fast-Path.
     */
    public function show(int $id): JsonResponse
    {
        $item = ChatbotFastPath::findOrFail($id);

        return response()->json([
            'success' => true,
            'data'    => $item,
        ]);
    }

    /**
     * Memperbarui data Fast-Path FAQ.
     */
    public function update(Request $request, int $id): JsonResponse
    {
        $item = ChatbotFastPath::findOrFail($id);

        $validated = $request->validate([
            'category'      => 'sometimes|required|string|in:general,layanan,sop,faq',
            'title'         => 'sometimes|required|string|max:150',
            'keywords'      => 'sometimes|required|string',
            'response_text' => 'sometimes|required|string',
            'is_active'     => 'boolean',
            'sort_order'    => 'integer',
        ]);

        $item->update($validated);

        return response()->json([
            'success' => true,
            'message' => 'Fast-Path FAQ berhasil diperbarui.',
            'data'    => $item,
        ]);
    }

    /**
     * Toggle status aktif / nonaktif.
     */
    public function toggle(int $id): JsonResponse
    {
        $item = ChatbotFastPath::findOrFail($id);
        $item->is_active = !$item->is_active;
        $item->save();

        return response()->json([
            'success' => true,
            'message' => 'Status Fast-Path berhasil diubah.',
            'data'    => $item,
        ]);
    }

    /**
     * Menghapus data Fast-Path FAQ.
     */
    public function destroy(int $id): JsonResponse
    {
        $item = ChatbotFastPath::findOrFail($id);
        $item->delete();

        return response()->json([
            'success' => true,
            'message' => 'Fast-Path FAQ berhasil dihapus.',
        ]);
    }
}
