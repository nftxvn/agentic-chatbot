<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatLog;
use Illuminate\Http\Request;

class ChatLogController extends Controller
{
    /**
     * GET /api/chat-logs — Paginated list of chat logs with search & filters
     */
    public function index(Request $request)
    {
        $query = ChatLog::with('apiKey:id,name')->orderBy('created_at', 'desc');

        // Filter channel
        if ($request->filled('channel') && $request->channel !== 'all') {
            $query->where('channel', $request->channel);
        }

        // Filter fallback status
        if ($request->filled('is_fallback')) {
            $isFallback = filter_var($request->is_fallback, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
            if ($isFallback !== null) {
                $query->where('is_fallback', $isFallback);
            }
        }

        // Search text in query or answer
        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('query', 'like', "%{$search}%")
                  ->orWhere('answer', 'like', "%{$search}%")
                  ->orWhere('sender_identifier', 'like', "%{$search}%");
            });
        }

        $perPage = min(max((int) $request->input('per_page', 20), 5), 100);
        $logs = $query->paginate($perPage);

        return response()->json([
            'success' => true,
            'data' => $logs->items(),
            'pagination' => [
                'current_page' => $logs->currentPage(),
                'last_page' => $logs->lastPage(),
                'per_page' => $logs->perPage(),
                'total' => $logs->total(),
            ],
        ]);
    }

    /**
     * GET /api/chat-logs/analytics — Aggregate metrics & top unanswered questions
     */
    public function analytics()
    {
        $totalQueries = ChatLog::count();
        $whatsappCount = ChatLog::where('channel', 'whatsapp')->count();
        $telegramCount = ChatLog::where('channel', 'telegram')->count();
        $apiCount = ChatLog::where('channel', 'api_v1')->count();
        $fallbackCount = ChatLog::where('is_fallback', true)->count();

        $fallbackRate = $totalQueries > 0 ? round(($fallbackCount / $totalQueries) * 100, 1) : 0;
        $avgResponseTime = (int) round(ChatLog::whereNotNull('response_time_ms')->avg('response_time_ms') ?? 0);

        $recentFallbacks = ChatLog::where('is_fallback', true)
            ->orderBy('created_at', 'desc')
            ->limit(6)
            ->get(['id', 'query', 'channel', 'created_at']);

        return response()->json([
            'success' => true,
            'data' => [
                'total_queries' => $totalQueries,
                'whatsapp_count' => $whatsappCount,
                'telegram_count' => $telegramCount,
                'api_count' => $apiCount,
                'fallback_count' => $fallbackCount,
                'fallback_rate_pct' => $fallbackRate,
                'avg_response_time_ms' => $avgResponseTime,
                'recent_fallbacks' => $recentFallbacks,
            ],
        ]);
    }

    /**
     * DELETE /api/chat-logs/{id} — Delete single log entry
     */
    public function destroy($id)
    {
        $log = ChatLog::findOrFail($id);
        $log->delete();

        return response()->json([
            'success' => true,
            'message' => 'Log riwayat percakapan berhasil dihapus.',
        ]);
    }

    /**
     * DELETE /api/chat-logs — Purge all logs
     */
    public function purge()
    {
        ChatLog::truncate();

        return response()->json([
            'success' => true,
            'message' => 'Seluruh riwayat percakapan berhasil dibersihkan.',
        ]);
    }
}
