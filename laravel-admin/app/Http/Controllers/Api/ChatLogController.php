<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ChatLog;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class ChatLogController extends Controller
{
    /**
     * GET /api/chat-logs — Telemetry transaction logs (Privacy-first: zero citizen text stored)
     */
    public function index(Request $request)
    {
        $query = ChatLog::with('apiKey:id,name')
            ->select(['id', 'created_at', 'channel', 'sender_identifier', 'api_key_id', 'is_fallback', 'response_time_ms'])
            ->orderBy('created_at', 'desc');

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

        // Filter by sender / client name
        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('sender_identifier', 'like', "%{$search}%")
                  ->orWhere('channel', 'like', "%{$search}%");
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
     * GET /api/chat-logs/analytics — Aggregate metrics & volume telemetry
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

        // Daily volume breakdown for the last 7 days (Privacy-safe aggregated counts)
        $dailyVolume = ChatLog::select(
            DB::raw('DATE(created_at) as date'),
            DB::raw('count(*) as total'),
            DB::raw('sum(case when is_fallback = 1 then 1 else 0 end) as fallbacks')
        )
            ->where('created_at', '>=', now()->subDays(7))
            ->groupBy(DB::raw('DATE(created_at)'))
            ->orderBy('date', 'asc')
            ->get();

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
                'daily_volume' => $dailyVolume,
            ],
        ]);
    }

    /**
     * DELETE /api/chat-logs/{id} — Delete single telemetry log entry
     */
    public function destroy($id)
    {
        $log = ChatLog::findOrFail($id);
        $log->delete();

        return response()->json([
            'success' => true,
            'message' => 'Catatan telemetri berhasil dihapus.',
        ]);
    }

    /**
     * DELETE /api/chat-logs/purge — Purge all telemetry logs
     */
    public function purge()
    {
        ChatLog::truncate();

        return response()->json([
            'success' => true,
            'message' => 'Seluruh data telemetri interaksi berhasil dibersihkan.',
        ]);
    }
}
