<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;

class DocumentCategoryController extends Controller
{
    public function index()
    {
        $categories = \App\Models\DocumentCategory::orderBy('name')->get();
        return response()->json([
            'success' => true,
            'data' => $categories
        ]);
    }

    public function store(Request $request)
    {
        $validated = $request->validate([
            'name' => 'required|string|unique:document_categories,name',
            'description' => 'nullable|string',
            'vision_prompt' => 'nullable|string',
            'llm_prompt' => 'nullable|string',
            'prompt_variables' => 'nullable',
            'ui_layout' => 'required|string',
            'vision_model' => 'nullable|string',
            'llm_model' => 'nullable|string',
            'temperature' => 'nullable|numeric|min:0|max:2',
            'chunk_size' => 'nullable|integer|min:100',
            'chunk_overlap' => 'nullable|integer|min:0',
        ]);

        $category = \App\Models\DocumentCategory::create($validated);
        return response()->json(['success' => true, 'data' => $category]);
    }

    public function update(Request $request, $id)
    {
        $category = \App\Models\DocumentCategory::findOrFail($id);
        
        $validated = $request->validate([
            'name' => 'required|string|unique:document_categories,name,'.$id,
            'description' => 'nullable|string',
            'vision_prompt' => 'nullable|string',
            'llm_prompt' => 'nullable|string',
            'prompt_variables' => 'nullable',
            'ui_layout' => 'required|string',
            'vision_model' => 'nullable|string',
            'llm_model' => 'nullable|string',
            'temperature' => 'nullable|numeric|min:0|max:2',
            'chunk_size' => 'nullable|integer|min:100',
            'chunk_overlap' => 'nullable|integer|min:0',
        ]);

        $category->update($validated);
        return response()->json(['success' => true, 'data' => $category]);
    }

    public function destroy($id)
    {
        $category = \App\Models\DocumentCategory::findOrFail($id);
        $category->delete();
        return response()->json(['success' => true, 'message' => 'Kategori dihapus.']);
    }
}
