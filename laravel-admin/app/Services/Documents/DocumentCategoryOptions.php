<?php

namespace App\Services\Documents;

use App\Models\Document;
use App\Models\DocumentCategory;

/** Map category settings to Python's extraction payload, including legacy keywords. */
class DocumentCategoryOptions
{
    /**
     * Build category extraction options for Python AI.
     */
    public function forDocument(Document $document): array
    {
        $category = $document->category;
        if (!$category && $document->category_id) {
            $category = DocumentCategory::find($document->category_id);
        }

        // Python expects comma-separated text; the new key takes precedence over job_titles.
        $kataKunci = data_get($category, 'prompt_variables.kata_kunci')
            ?? data_get($category, 'prompt_variables.job_titles', []);
        $customPrompts = data_get($category, 'prompt_variables.custom_prompts', []);

        return [
            'category_prompt' => $category?->vision_prompt,
            'job_titles'      => is_array($kataKunci) ? implode(', ', $kataKunci) : $kataKunci,
            'vision_model'    => $category?->vision_model,
            'custom_prompts'  => !empty($customPrompts) ? $customPrompts : null,
        ];
    }

}
