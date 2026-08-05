<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use App\Services\AiMicroserviceClient;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class FlowchartController extends Controller
{
    /**
     * Get the flowchart data for a document.
     */
    public function show(int $id)
    {
        $document = Document::findOrFail($id);

        return response()->json([
            'success' => true,
            'data' => [
                'flowchart_data' => $document->flowchart_data,
                'flowchart_status' => $document->flowchart_status,
            ],
        ]);
    }

    /**
     * Save the flowchart data as draft.
     */
    public function update(Request $request, int $id)
    {
        $request->validate([
            'nodes' => 'present|array',
            'edges' => 'present|array',
        ]);

        $document = Document::findOrFail($id);

        $document->update([
            'flowchart_data' => [
                'nodes' => $request->nodes,
                'edges' => $request->edges,
            ],
            'flowchart_status' => 'draft',
        ]);

        return response()->json([
            'success' => true,
            'message' => 'Flowchart berhasil disimpan sebagai draf.',
        ]);
    }

    /**
     * Finalize the flowchart and embed into ChromaDB.
     */
    public function finalize(Request $request, int $id, AiMicroserviceClient $aiClient)
    {
        $document = Document::findOrFail($id);

        if (empty($document->flowchart_data) || empty($document->flowchart_data['nodes'])) {
            return response()->json([
                'success' => false,
                'message' => 'Flowchart tidak boleh kosong.',
            ], 422);
        }

        $nodes = $document->flowchart_data['nodes'];
        $edges = $document->flowchart_data['edges'] ?? [];

        $markdown = $this->flowchartToMarkdown($nodes, $edges);

        $document->update([
            'flowchart_markdown' => $markdown,
            'flowchart_status' => 'finalized',
        ]);

        $aiResponse = $aiClient->reEmbedDocument($document->id, $markdown);

        if (!$aiResponse['success']) {
            Log::warning('Failed to re-embed flowchart document', [
                'document_id' => $document->id,
                'error' => $aiResponse['message'] ?? 'Unknown error',
            ]);
            // Still return success because it's finalized
        }

        return response()->json([
            'success' => true,
            'message' => 'Flowchart berhasil difinalisasi.',
        ]);
    }

    /**
     * Convert flowchart JSON nodes and edges to markdown.
     */
    protected function flowchartToMarkdown(array $nodes, array $edges): string
    {
        // Extract unique pelaksana
        $pelaksanaList = [];
        foreach ($nodes as $node) {
            if (!empty($node['data']['pelaksana'])) {
                $pelaksanaList[] = $node['data']['pelaksana'];
            }
        }
        $pelaksanaList = array_unique($pelaksanaList);
        $pelaksanaStr = implode(' | ', $pelaksanaList);

        $md = "# SOP Flowchart\n\n";
        if (!empty($pelaksanaStr)) {
            $md .= "**Pelaksana:** {$pelaksanaStr}\n\n";
        }
        $md .= "---\n\n";

        // Map nodes by id for quick lookup
        $nodesById = [];
        foreach ($nodes as $node) {
            $nodesById[$node['id']] = $node;
        }

        // Map edges by source for quick lookup
        $edgesBySource = [];
        foreach ($edges as $edge) {
            $source = $edge['source'];
            if (!isset($edgesBySource[$source])) {
                $edgesBySource[$source] = [];
            }
            $edgesBySource[$source][] = $edge;
        }

        // Sort nodes by stepNo if available
        usort($nodes, function ($a, $b) {
            $aStep = $a['data']['stepNo'] ?? 999;
            $bStep = $b['data']['stepNo'] ?? 999;
            return $aStep <=> $bStep;
        });

        foreach ($nodes as $node) {
            $data = $node['data'] ?? [];
            $stepNo = $data['stepNo'] ?? '?';
            $shapeType = 'Proses';
            if (isset($data['shape']) && $data['shape'] === 'diamond') {
                $shapeType = 'Keputusan';
            } elseif (isset($data['shape']) && $data['shape'] === 'pill') {
                $shapeType = 'Mulai/Selesai';
            }

            $pelaksana = $data['pelaksana'] ?? '';
            $md .= "**Langkah {$stepNo}** [{$shapeType}]";
            if ($pelaksana) {
                $md .= " — Pelaksana: {$pelaksana}";
            }
            $md .= "  \n";

            $waktu = $data['waktu'] ?? '';
            $output = $data['output'] ?? '';
            $waktuOutput = [];
            if ($waktu) {
                $waktuOutput[] = "Waktu: {$waktu}";
            }
            if ($output) {
                $waktuOutput[] = "Output: {$output}";
            }
            if (!empty($waktuOutput)) {
                $md .= implode(' | ', $waktuOutput) . "\n";
            }

            $label = $data['label'] ?? '';
            if ($label) {
                $md .= "{$label}\n";
            }

            // Find outgoing edges
            if (isset($edgesBySource[$node['id']])) {
                $outgoingEdges = $edgesBySource[$node['id']];
                if (count($outgoingEdges) == 1) {
                    $targetNode = $nodesById[$outgoingEdges[0]['target']] ?? null;
                    if ($targetNode) {
                        $targetStep = $targetNode['data']['stepNo'] ?? '?';
                        $md .= "→ Lanjut ke Langkah {$targetStep}\n";
                    }
                } elseif (count($outgoingEdges) > 1) {
                    foreach ($outgoingEdges as $edge) {
                        $targetNode = $nodesById[$edge['target']] ?? null;
                        if ($targetNode) {
                            $targetStep = $targetNode['data']['stepNo'] ?? '?';
                            $edgeLabel = $edge['label'] ?? '';
                            if ($edgeLabel) {
                                $md .= "- {$edgeLabel} → Langkah {$targetStep}\n";
                            } else {
                                $md .= "- → Langkah {$targetStep}\n";
                            }
                        }
                    }
                }
            }

            $md .= "\n";
        }

        return trim($md);
    }
}
