import { useHardwareMonitoring } from "../hooks/monitoring/useHardwareMonitoring";
import { useTelemetryMonitoring } from "../hooks/monitoring/useTelemetryMonitoring";
import { Link, useSearchParams } from 'react-router-dom'
import ConfirmModal from '../components/ConfirmModal'
import { InfoTooltip } from '../components/UI/InfoTooltip'
import { SlidingTabs } from '../components/UI/SlidingTabs'

export default function MonitoringPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeMainTab = searchParams.get('tab') === 'hardware' ? 'hardware' : 'telemetri'

  const handleTabChange = (newTab) => {
    setSearchParams({ tab: newTab }, { replace: true })
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-20">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>MONITORING & OBSERVABILITAS</span>
            <InfoTooltip
              size="lg"
              content="Pemantauan telemetri beban kueri, latensi inferensi LLM, distribusi kanal komunikasi, serta kondisi perangkat keras & runtime model AI secara terpadu."
            />
          </h1>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start md:self-auto">
          {activeMainTab === 'hardware' && (
            <Link
              to="/settings/chatbot"
              className="px-3.5 py-2 text-xs font-semibold rounded-xl text-[var(--text-secondary)] hover:text-sky-500 hover:bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Pengaturan AI</span>
            </Link>
          )}
        </div>
      </div>

      {/* ── TOP-LEVEL SEGMENTED TABS ────────────────────────────── */}
      <SlidingTabs
        tabs={[
          { id: 'telemetri', label: 'Telemetri Layanan' },
          { id: 'hardware', label: 'Hardware & Runtime' },
        ]}
        activeTab={activeMainTab}
        onChange={handleTabChange}
        variant="underline"
      />

      {/* ── TAB CONTENT: TELEMETRI ──────────────────────────────── */}
      {activeMainTab === 'telemetri' && <TelemetrySection />}

      {/* ── TAB CONTENT: HARDWARE ───────────────────────────────── */}
      {activeMainTab === 'hardware' && <HardwareSection />}
    </div>
  )
}

/* ========================================================================== */
/* SUB-KOMPONEN: TELEMETRI SECTION                                            */
/* ========================================================================== */
function TelemetrySection() {
  const {
    logs,
    analytics,
    pagination,
    loading,
    statusMsg,
    setStatusMsg,
    channelFilter,
    setChannelFilter,
    fallbackFilter,
    setFallbackFilter,
    searchQuery,
    setSearchQuery,
    page,
    setPage,
    deleteTarget,
    setDeleteTarget,
    showPurgeModal,
    setShowPurgeModal,
    statsRef,
    handleSearchSubmit,
    handleDelete,
    handlePurge,
  } = useTelemetryMonitoring();

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── STATUS ALERT ────────────────────────────────────────── */}
      {statusMsg && (
        <div className="p-3.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] flex items-center justify-between text-xs text-[var(--red-color)]">
          <span>{statusMsg.text}</span>
          <button
            type="button"
            onClick={() => setStatusMsg(null)}
            className="text-xs font-bold underline cursor-pointer"
          >
            Tutup
          </button>
        </div>
      )}

      {/* ── TOP STATS ANALYTICS ─────────────────────────────────── */}
      <div ref={statsRef} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5 sm:gap-4">
        {[
          {
            label: 'Total Kueri',
            value: analytics ? analytics.total_queries.toLocaleString('id-ID') : '0',
            dotColor: 'bg-sky-500',
            tooltip: 'Jumlah total transaksi kueri yang diproses oleh AI Microservice.',
          },
          {
            label: 'Kanal WhatsApp',
            value: analytics ? analytics.whatsapp_count.toLocaleString('id-ID') : '0',
            dotColor: 'bg-emerald-500',
            tooltip: 'Total kueri yang masuk melalui webhook WhatsApp Gateway.',
          },
          {
            label: 'Kanal Telegram',
            value: analytics ? (analytics.telegram_count ?? 0).toLocaleString('id-ID') : '0',
            dotColor: 'bg-cyan-500',
            tooltip: 'Total kueri yang masuk melalui bot Telegram.',
          },
          {
            label: 'Public API Gateway',
            value: analytics ? analytics.api_count.toLocaleString('id-ID') : '0',
            dotColor: 'bg-indigo-400',
            tooltip: 'Jumlah pemanggilan endpoint API /api/v1/chat dari aplikasi eksternal.',
          },
          {
            label: 'Rata-Rata Latensi',
            value: analytics ? `${analytics.avg_response_time_ms} ms` : '0 ms',
            dotColor: 'bg-violet-500',
            tooltip: 'Waktu rata-rata inferensi pencarian vektor & generasi teks LLM.',
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 sm:p-5 rounded-xl flex flex-col justify-between hover:border-[var(--text-muted)]/40 transition-all duration-200 shadow-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center">
                <span>{stat.label}</span>
                <InfoTooltip content={stat.tooltip} />
              </span>
              <span className={`w-2 h-2 rounded-full ${stat.dotColor} shrink-0`} />
            </div>
            <div className="text-2xl font-black text-[var(--text-primary)] tracking-tight mt-3">
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── FILTER & SEARCH BAR ─────────────────────────────────── */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="w-full md:w-80 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari kanal atau nama pengirim..."
              className="w-full pl-9 pr-3.5 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
            />
            <svg className="w-4 h-4 text-[var(--text-muted)] absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
          </div>

          <div className="flex items-center gap-2.5 w-full md:w-auto justify-end flex-wrap">
            {/* Channel filter */}
            <select
              value={channelFilter}
              onChange={(e) => {
                setChannelFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none cursor-pointer"
            >
              <option value="all">Semua Kanal</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="telegram">Telegram</option>
              <option value="api_v1">Public API</option>
            </select>

            {/* Fallback filter */}
            <select
              value={fallbackFilter}
              onChange={(e) => {
                setFallbackFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none cursor-pointer"
            >
              <option value="all">Semua Status</option>
              <option value="success">Terjawab Otomatis (SOP)</option>
              <option value="fallback">Perlu Tindak Lanjut Petugas</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white transition-all hover:scale-[1.02] cursor-pointer shadow-md shadow-sky-500/25"
            >
              Cari
            </button>

            {logs.length > 0 && (
              <button
                type="button"
                onClick={() => setShowPurgeModal(true)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-[var(--red-color)] hover:bg-[var(--bg-card)] bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
                <span>Kosongkan Log</span>
              </button>
            )}
          </div>
        </form>
      </div>

      {/* ── LOGS TABLE CARD ─────────────────────────────────────── */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[var(--border-color)] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-[var(--text-primary)]">
              Log Transaksi Telemetri
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Total {pagination.total} transaksi tercatat secara anonim.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="p-8 space-y-3">
            <div className="skeleton h-8 w-full rounded-lg" />
            <div className="skeleton h-8 w-full rounded-lg" />
            <div className="skeleton h-8 w-full rounded-lg" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <p className="text-xs font-semibold text-[var(--text-primary)]">Belum ada transaksi telemetri</p>
            <p className="text-xs text-[var(--text-muted)]">
              Aktivitas kueri dari WhatsApp bot, Telegram bot, atau Public API akan otomatis tercatat di sini.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border-color)] bg-[var(--bg-input)]/40 text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-3 px-4">Waktu Transaksi</th>
                  <th className="py-3 px-4">Kanal</th>
                  <th className="py-3 px-4">Sumber / Klien</th>
                  <th className="py-3 px-4">Status Layanan</th>
                  <th className="py-3 px-4">Latensi Inferensi</th>
                  <th className="py-3 px-4 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)] text-xs text-[var(--text-primary)]">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[var(--bg-input)] transition-colors">
                    <td className="py-3.5 px-4 text-xs text-[var(--text-muted)] whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('id-ID')}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {log.channel === 'whatsapp' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
                          WhatsApp
                        </span>
                      ) : log.channel === 'telegram' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-cyan-600 dark:text-cyan-400 bg-cyan-500/10">
                          Telegram
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-indigo-600 dark:text-indigo-400 bg-indigo-500/10">
                          Public API
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-[var(--text-secondary)] whitespace-nowrap">
                      {log.sender_identifier || (log.api_key?.name ? `API: ${log.api_key.name}` : '-')}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {log.is_fallback ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                          Perlu Tindak Lanjut Petugas
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          Terjawab Otomatis (SOP)
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-xs font-mono text-[var(--text-muted)] whitespace-nowrap">
                      {log.response_time_ms ? (
                        <span className="font-semibold text-[var(--text-primary)]">
                          {log.response_time_ms} ms
                        </span>
                      ) : '-'}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(log)}
                        className="p-1 text-zinc-400 hover:text-rose-500 rounded transition-colors cursor-pointer"
                        title="Hapus Catatan"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination footer */}
        {pagination.last_page > 1 && (
          <div className="p-4 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
            <span className="text-[var(--text-muted)]">
              Halaman {pagination.current_page} dari {pagination.last_page}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] disabled:opacity-50 cursor-pointer"
              >
                Sebelumnya
              </button>
              <button
                type="button"
                disabled={page >= pagination.last_page}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] disabled:opacity-50 cursor-pointer"
              >
                Berikutnya
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── MODAL DELETE SINGLE ─────────────────────────────────── */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Hapus Catatan Telemetri?"
        message="Apakah Anda yakin ingin menghapus data baris telemetri ini?"
        confirmText="Ya, Hapus"
        cancelText="Batal"
        danger={true}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* ── MODAL PURGE ALL ─────────────────────────────────────── */}
      <ConfirmModal
        isOpen={showPurgeModal}
        title="Bersihkan Seluruh Data Telemetri?"
        message="Tindakan ini akan mengosongkan seluruh data metrik telemetri interaksi dari database secara permanen."
        confirmText="Ya, Bersihkan Semua"
        cancelText="Batal"
        danger={true}
        onConfirm={handlePurge}
        onCancel={() => setShowPurgeModal(false)}
      />
    </div>
  )
}

/* ========================================================================== */
/* SUB-KOMPONEN: HARDWARE SECTION                                             */
/* ========================================================================== */
function HardwareSection() {
  const {
    data,
    loading,
    refreshing,
    error,
    lastUpdated,
    activeTab,
    setActiveTab,
    autoRefresh,
    setAutoRefresh,
    statsGridRef,
    fetchDiagnostics,
    cfg,
    gpu,
    ram,
    oll,
    sistem,
    sys,
    isLoaded,
    isFullGpu,
    vramTotal,
    vramUsed,
    vramFree,
    vramPercent,
    ramTotal,
    ramUsed,
    ramFree,
    ramPercent,
    modelMib,
    kvCacheMib,
    cudaBufferMib,
    modelWidthPercent,
    kvWidthPercent,
    cudaWidthPercent,
  } = useHardwareMonitoring();

  if (loading && !data) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl space-y-3">
              <div className="skeleton h-4 w-24 rounded-md" />
              <div className="skeleton h-8 w-36 rounded-lg" />
              <div className="skeleton h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
        <div className="p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl space-y-4">
          <div className="skeleton h-8 w-48 rounded-lg" />
          <div className="skeleton h-40 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── REFRESH / ACTION TOOLBAR ────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 p-3.5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl">
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span>
            {lastUpdated ? `Diperbarui: ${lastUpdated.toLocaleTimeString('id-ID')}` : 'Memeriksa...'}
          </span>
          <span>·</span>
          <label className="inline-flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="accent-sky-500 rounded cursor-pointer"
            />
            <span>Auto-refresh (15d)</span>
          </label>
        </div>

        <button
          type="button"
          onClick={() => fetchDiagnostics(true)}
          disabled={refreshing}
          className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] cursor-pointer disabled:opacity-50"
        >
          <svg
            className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{refreshing ? 'Memperbarui...' : 'Segarkan Data'}</span>
        </button>
      </div>

      {/* ── ERROR BANNER ────────────────────────────────────────── */}
      {error && (
        <div className="p-3.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] flex items-center justify-between text-xs text-[var(--red-color)]">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => fetchDiagnostics(true)}
            className="px-2.5 py-1 text-xs font-bold rounded-lg bg-[var(--red-color)] text-white hover:opacity-90 transition-opacity cursor-pointer"
          >
            Coba Lagi
          </button>
        </div>
      )}

      {/* ── METRICS GRID (4 CARDS) ──────────────────────────────── */}
      <div ref={statsGridRef} className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4">
        {/* Card 1: VRAM GPU */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-xl flex flex-col justify-between shadow-xs hover:border-sky-500 transition-all">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  VRAM GPU NVIDIA
                </span>
                <InfoTooltip content="Status memori grafis (VRAM) yang digunakan untuk menampung bobot model LLM, KV Cache percakapan, dan buffer CUDA." />
              </div>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <div>
              <div className="text-2xl font-black text-[var(--text-primary)] tracking-tight">
                {gpu ? `${(vramUsed / 1024).toFixed(1)} / ${(vramTotal / 1024).toFixed(1)} GB` : 'CPU Mode'}
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                {gpu ? `Bebas: ${(vramFree / 1024).toFixed(1)} GB (${vramPercent}% terpakai)` : 'Tanpa akselerasi GPU'}
              </p>
            </div>
          </div>
          <div className="pt-3">
            <span className="text-[11px] font-mono text-[var(--text-secondary)] block truncate">
              {gpu ? gpu.nama.replace('NVIDIA GeForce ', '') : 'Host CPU'}
            </span>
          </div>
        </div>

        {/* Card 2: RAM Sistem */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-xl flex flex-col justify-between shadow-xs hover:border-sky-500 transition-all">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  RAM Sistem Host
                </span>
                <InfoTooltip content="Pemakaian memori RAM server untuk sistem operasi, daemon Ollama, Laravel backend, dan Python FastAPI." />
              </div>
              <span className="w-2 h-2 rounded-full bg-sky-500" />
            </div>
            <div>
              <div className="text-2xl font-black text-[var(--text-primary)] tracking-tight">
                {(ramUsed / 1024).toFixed(1)} / {(ramTotal / 1024).toFixed(1)} GB
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Bebas: {(ramFree / 1024).toFixed(1)} GB ({ramPercent}% terpakai)
              </p>
            </div>
          </div>
          <div className="pt-3">
            <span className="text-[11px] font-mono text-[var(--text-secondary)] block">
              OS: {sys?.is_wsl ? 'WSL2 (Linux Kernel)' : 'Linux Native'}
            </span>
          </div>
        </div>

        {/* Card 3: Model LLM Aktif */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-xl flex flex-col justify-between shadow-xs hover:border-sky-500 transition-all">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  Model LLM Aktif
                </span>
                <InfoTooltip content="Model bahasa kecerdasan buatan yang saat ini dimuat ke memori kerja beserta persentase layer komputasi yang di-offload ke GPU." />
              </div>
              <span className="w-2 h-2 rounded-full bg-purple-500" />
            </div>
            <div>
              <div className="text-2xl font-black text-[var(--text-primary)] tracking-tight truncate" title={cfg?.llm_model || 'qwen3:8b'}>
                {cfg?.llm_model || 'qwen3:8b'}
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                {isLoaded ? `Offload: ${oll.persen_di_gpu}% GPU (${oll.di_gpu_mib} MiB)` : 'Idle (siap inferensi)'}
              </p>
            </div>
          </div>
          <div className="pt-3">
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded-md border inline-flex items-center gap-1 ${
                isFullGpu
                  ? 'bg-[var(--bg-input)] text-[var(--action-green)] border-[var(--border-color)]'
                  : isLoaded
                  ? 'bg-[var(--bg-input)] text-[var(--yellow-color)] border-[var(--border-color)]'
                  : 'bg-[var(--bg-input)] text-[var(--text-muted)] border-[var(--border-color)]'
              }`}
            >
              {isFullGpu ? '100% Akselerasi GPU' : isLoaded ? 'Parsial GPU/CPU' : 'Siap Digunakan'}
            </span>
          </div>
        </div>

        {/* Card 4: Jendela Konteks */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-xl flex flex-col justify-between shadow-xs hover:border-sky-500 transition-all">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  Jendela Konteks
                </span>
                <InfoTooltip content="Batas token memori percakapan dan dokumen SOP dalam satu kali inferensi query (1 token ≈ 3-4 karakter)." />
              </div>
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>
            <div>
              <div className="text-2xl font-black text-[var(--text-primary)] tracking-tight">
                {(cfg?.num_ctx || 6144).toLocaleString('id-ID')} Token
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Kapasitas memori RAG per query
              </p>
            </div>
          </div>
          <div className="pt-3 flex items-center justify-between text-[11px]">
            <span className="text-[var(--text-muted)]">Estimasi:</span>
            <span className="font-bold text-[var(--text-primary)]">
              ~{Math.round((cfg?.num_ctx || 6144) * 3).toLocaleString('id-ID')} Karakter
            </span>
          </div>
        </div>
      </div>

      {/* ── SUB-TABS NAVIGATION & DETAILS ───────────────────────── */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-4 sm:p-5 shadow-xs space-y-4">
        <SlidingTabs
          tabs={[
            { id: 'hardware', label: 'VRAM & Hardware' },
            { id: 'ollama', label: 'Runtime Ollama' },
            { id: 'config', label: 'Konfigurasi' },
          ]}
          activeTab={activeTab}
          onChange={setActiveTab}
          variant="underline"
        />

        {/* ── TAB 1: VRAM & HARDWARE ─────────────────────────────── */}
        {activeTab === 'hardware' && (
          <div className="space-y-4 animate-fade-in text-xs">
            {/* Visual Bar VRAM (Hanya tampil jika ada GPU) */}
            {gpu ? (
              <div className="p-3.5 sm:p-4 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <span className="text-xs font-bold text-[var(--text-primary)]">
                      Alokasi VRAM GPU ({gpu.nama.replace('NVIDIA GeForce ', '')})
                    </span>
                    <InfoTooltip content="Visualisasi pembagian kapasitas VRAM untuk bobot model LLM, buffer perhatian KV cache, CUDA runtime, dan sisa VRAM bebas." />
                  </div>
                  <span className="font-bold text-xs text-[var(--text-primary)]">
                    {vramUsed} / {vramTotal} MiB
                  </span>
                </div>

                {/* Stacked Progress Bar */}
                {isLoaded ? (
                  <>
                    <div className="h-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] overflow-hidden flex shadow-inner">
                      <div
                        className="bg-indigo-500 h-full flex items-center justify-center text-[10px] text-white font-bold transition-all"
                        style={{ width: `${modelWidthPercent}%` }}
                        title={`Model: ~${modelMib} MiB`}
                      >
                        {modelWidthPercent > 15 ? `Model (${(modelMib / 1024).toFixed(1)} GB)` : ''}
                      </div>
                      <div
                        className="bg-sky-500 h-full flex items-center justify-center text-[10px] text-white font-bold transition-all"
                        style={{ width: `${kvWidthPercent}%` }}
                        title={`KV Cache: ~${kvCacheMib} MiB`}
                      >
                        {kvWidthPercent > 8 ? 'KV' : ''}
                      </div>
                      <div
                        className="bg-amber-500 h-full flex items-center justify-center text-[10px] text-white font-bold transition-all"
                        style={{ width: `${cudaWidthPercent}%` }}
                        title={`CUDA & Buffer: ~${cudaBufferMib} MiB`}
                      >
                        {cudaWidthPercent > 6 ? 'CUDA' : ''}
                      </div>
                      <div
                        className="bg-[var(--action-green)] h-full flex items-center justify-center text-[10px] text-white font-bold transition-all flex-1"
                        title={`Bebas: ${vramFree} MiB`}
                      >
                        {vramFree > 500 ? 'Bebas' : ''}
                      </div>
                    </div>

                    {/* Legend Chips (Active) */}
                    <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-indigo-500 shrink-0" />
                        <span className="text-[var(--text-secondary)]">Model ({(modelMib / 1024).toFixed(1)} GB)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-sky-500 shrink-0" />
                        <span className="text-[var(--text-secondary)]">KV Cache ({kvCacheMib} MB)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-[var(--yellow-color)] shrink-0" />
                        <span className="text-[var(--text-secondary)]">CUDA Buffer ({cudaBufferMib} MB)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-[var(--action-green)] shrink-0" />
                        <span className="text-[var(--text-secondary)]">Bebas (~{vramFree} MB)</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="h-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] overflow-hidden flex shadow-inner">
                      <div
                        className="bg-[var(--yellow-color)] h-full flex items-center justify-center text-[10px] text-white font-bold transition-all"
                        style={{ width: `${Math.max(3, vramPercent)}%` }}
                        title={`Sistem Host: ${vramUsed} MiB`}
                      >
                        {vramPercent > 10 ? 'Sistem' : ''}
                      </div>
                      <div
                        className="bg-[var(--bg-card)] h-full flex items-center justify-center text-[10px] text-[var(--action-green)] font-bold transition-all flex-1"
                        title={`VRAM Bebas: ${vramFree} MiB`}
                      >
                        VRAM Bebas ({vramFree} MiB)
                      </div>
                    </div>

                    {/* Legend Chips (Standby) */}
                    <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-[var(--yellow-color)] shrink-0" />
                        <span className="text-[var(--text-secondary)]">Sistem Host ({vramUsed} MB)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-[var(--action-green)] shrink-0" />
                        <span className="text-[var(--text-secondary)]">VRAM Bebas ({vramFree} MB)</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-sm bg-[var(--brand-primary)] shrink-0" />
                        <span className="text-[var(--text-muted)]">Model Siap Inferensi (~{(modelMib / 1024).toFixed(1)} GB)</span>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--yellow-color)] text-xs">
                Mode CPU: Tidak ada GPU NVIDIA terdeteksi. Inferensi berjalan sepenuhnya menggunakan prosesor dan RAM host.
              </div>
            )}

            {/* Hardware Specs Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {/* GPU NVIDIA */}
              <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2.5">
                <div className="flex items-center">
                  <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                    GPU NVIDIA
                  </span>
                  <InfoTooltip content="Rincian kartu grafis NVIDIA yang menggerakkan inferensi lokal dan status akselerasi Flash Attention." />
                </div>
                <div className="space-y-1.5 divide-y divide-[var(--border-color)]">
                  <Row label="Model GPU" value={gpu?.nama || 'Mode CPU (Tanpa GPU)'} />
                  <Row label="Total VRAM" value={gpu ? `${vramTotal} MiB (${(vramTotal / 1024).toFixed(1)} GB)` : '—'} />
                  <Row label="VRAM Terpakai" value={gpu ? `${vramUsed} MiB` : '—'} />
                  <Row label="VRAM Bebas" value={gpu ? `${vramFree} MiB` : '—'} highlight={gpu && vramFree > 300 ? 'text-[var(--action-green)] font-bold' : 'text-[var(--yellow-color)] font-bold'} />
                  <Row label="Utilisasi GPU" value={gpu ? `${gpu.utilisasi_persen ?? 0}%` : '—'} />
                  <Row label="Flash Attention" value={cfg?.flash_attention === '1' ? 'Aktif (v1)' : 'Nonaktif'} />
                  <Row label="Kuantisasi KV" value={cfg?.kv_cache_type || 'q8_0'} />
                </div>
              </div>

              {/* Sistem & RAM */}
              <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2.5">
                <div className="flex items-center">
                  <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                    Sistem & RAM
                  </span>
                  <InfoTooltip content="Spesifikasi lingkungan OS, runtime bahasa Python, utilisasi RAM server, serta alokasi model embedding vektor." />
                </div>
                <div className="space-y-1.5 divide-y divide-[var(--border-color)]">
                  <Row label="Platform OS" value={sistem?.os_name || 'Linux Server'} />
                  <Row label="Python Runtime" value={sistem?.python_version ? `Python ${sistem.python_version}` : 'Python 3.12+'} />
                  <Row label="Total RAM" value={ram ? `${(ramTotal / 1024).toFixed(1)} GB (${ramTotal} MiB)` : '—'} />
                  <Row label="RAM Terpakai" value={ram ? `${(ramUsed / 1024).toFixed(1)} GB` : '—'} />
                  <Row label="RAM Bebas" value={ram ? `${(ramFree / 1024).toFixed(1)} GB` : '—'} highlight="text-emerald-500 font-bold" />
                  <Row label="Embedding Model" value={cfg?.embedding_model || 'BAAI/bge-m3'} />
                  <Row label="Embedding Device" value={`${cfg?.embedding_device || 'auto'} (${cfg?.embedding_device === 'cuda' ? 'GPU' : 'RAM CPU'})`} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: RUNTIME OLLAMA ──────────────────────────────── */}
        {activeTab === 'ollama' && (
          <div className="space-y-3 animate-fade-in text-xs">
            <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                    Runtime Ollama
                  </span>
                  <InfoTooltip content="Status daemon Ollama, endpoint API inferensi lokal, dan model AI yang sedang aktif di memori grafis." />
                </div>
                <span className="text-[11px] text-[var(--text-muted)]">
                  {cfg?.ollama_url || 'http://localhost:11434'}
                </span>
              </div>

              {!oll?.termuat ? (
                <div className="p-4 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-center space-y-1">
                  <p className="font-semibold text-[var(--text-primary)]">
                    Model belum aktif di VRAM
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    Ollama akan otomatis memuat model {cfg?.llm_model || 'AI'} saat pertanyaan pertama dikirim.
                  </p>
                </div>
              ) : (
                <div className="space-y-1.5 divide-y divide-[var(--border-color)]">
                  <Row label="Model Aktif" value={oll.nama} highlight="font-bold text-sky-500" />
                  <Row
                    label="Offload GPU"
                    value={`${oll.persen_di_gpu}%`}
                    highlight={oll.persen_di_gpu >= 99 ? 'text-emerald-500 font-bold' : 'text-amber-500 font-bold'}
                  />
                  <Row label="Ukuran VRAM" value={`${oll.di_gpu_mib} / ${oll.ukuran_mib} MiB`} />
                  <Row label="Jendela Konteks" value={`${oll.konteks ?? cfg?.num_ctx} Token`} />
                  <Row label="Keep-Alive" value="30 Menit" />
                  <Row label="Thinking Mode" value="Nonaktif (Default)" />
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 3: KONFIGURASI ─────────────────────────────────── */}
        {activeTab === 'config' && (
          <div className="space-y-3 animate-fade-in text-xs">
            <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2.5">
              <div className="flex items-center">
                <span className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                  Konfigurasi AI (python-ai/.env)
                </span>
                <InfoTooltip content="Parameter lingkungan (.env) yang mengatur konfigurasi arsitektur pipeline AI pada microservice Python." />
              </div>

              <div className="space-y-1.5 divide-y divide-[var(--border-color)]">
                <Row label="LLM Model" value={cfg?.llm_model} />
                <Row label="Vision Model" value={cfg?.vision_model} />
                <Row label="Embedding Model" value={cfg?.embedding_model} />
                <Row label="Embedding Device" value={cfg?.embedding_device} />
                <Row
                  label="Jendela Konteks (num_ctx)"
                  value={`${cfg?.num_ctx} Token`}
                  highlight="font-bold text-sky-500"
                />
                <Row
                  label="GPU Layers (num_gpu)"
                  value={cfg?.num_gpu_mode === 'auto-fit' ? 'Auto-Fit (Ollama)' : `${cfg?.num_gpu}`}
                />
                <Row label="Vector Storage" value={cfg?.chroma_dir || './data/chromadb'} />
                <Row label="Keamanan Endpoint" value="Bearer Token Aktif" highlight="text-emerald-500 font-semibold" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value, highlight }) {
  return (
    <div className="flex items-baseline justify-between gap-3 pt-1.5 first:pt-0">
      <span className="text-xs text-[var(--text-muted)] shrink-0">{label}</span>
      <span
        className={`text-xs text-right truncate ${
          highlight || 'text-[var(--text-primary)] font-medium'
        }`}
        title={String(value ?? '—')}
      >
        {value ?? '—'}
      </span>
    </div>
  )
}
