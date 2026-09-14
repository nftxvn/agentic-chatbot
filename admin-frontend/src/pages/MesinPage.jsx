import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { Link } from 'react-router-dom'
import gsap from 'gsap'
import { mesinApi } from '../api/mesin'
import { SlidingTabs } from '../components/UI/SlidingTabs'
import { addAppNotification } from '../utils/notifications'
import { InfoTooltip } from '../components/UI/InfoTooltip'

export default function MesinPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [activeTab, setActiveTab] = useState('hardware') // 'hardware' | 'ollama' | 'config'
  const [autoRefresh, setAutoRefresh] = useState(true)

  const headerRef = useRef(null)
  const statsGridRef = useRef(null)

  const fetchDiagnostics = async (isManual = false) => {
    if (isManual) setRefreshing(true)
    const startTime = Date.now()
    try {
      const res = await mesinApi.ambil()
      setData(res)
      setError(null)
      setLastUpdated(new Date())
      if (isManual) {
        addAppNotification({
          title: 'Diagnostik Mesin',
          message: 'Data perangkat keras dan model berhasil diperbarui.',
          type: 'system',
        })
      }
    } catch (e) {
      console.error('Gagal mengambil diagnostik mesin:', e)
      setError(
        e?.response?.status === 401
          ? 'Token otorisasi internal ditolak. Periksa INTERNAL_API_TOKEN.'
          : 'Layanan Python AI (Port 8080) tidak dapat dihubungi.'
      )
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => {
        setLoading(false)
        if (isManual) setRefreshing(false)
      }, Math.max(0, 250 - elapsed))
    }
  }

  useEffect(() => {
    fetchDiagnostics()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      // Hanya polling jika tab browser sedang aktif dilihat
      if (!document.hidden) {
        fetchDiagnostics(false)
      }
    }, 15000)

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // Segarkan data begitu tab dibuka kembali
        fetchDiagnostics(false)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [autoRefresh])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
    if (!loading && statsGridRef.current) {
      gsap.fromTo(
        statsGridRef.current.children,
        { opacity: 0, y: 12, scale: 0.98 },
        { opacity: 1, y: 0, scale: 1, duration: 0.4, stagger: 0.05, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  const cfg = data?.konfigurasi
  const gpu = data?.gpu
  const ram = data?.ram
  const oll = data?.ollama
  const rek = data?.rekomendasi
  const sistem = data?.sistem
  const sys = data?.sistem

  // Evaluasi Kondisi Kesehatan Mesin secara Dinamis
  const isLoaded = Boolean(oll?.termuat)
  const isFullGpu = isLoaded && (oll?.persen_di_gpu ?? 0) >= 99
  const isVramTight = Boolean(gpu && (gpu.vram_bebas_mib ?? 0) < 300)
  const isVramCritical = Boolean(gpu && (gpu.vram_bebas_mib ?? 0) < 100)

  // Persentase utilisasi memori dinamis
  const vramTotal = gpu?.vram_total_mib || 0
  const vramUsed = gpu?.vram_dipakai_mib || 0
  const vramFree = gpu?.vram_bebas_mib || 0
  const vramPercent = vramTotal > 0 ? Math.min(100, Math.round((vramUsed / vramTotal) * 100)) : 0

  const ramTotal = ram?.ram_total_mib || 0
  const ramUsed = ram?.ram_dipakai_mib || 0
  const ramFree = ram?.ram_bebas_mib || 0
  const ramPercent = ramTotal > 0 ? Math.min(100, Math.round((ramUsed / ramTotal) * 100)) : 0

  // Perhitungan Dinamis Visualisasi Alokasi VRAM (jika ada GPU)
  const modelMib = oll?.di_gpu_mib || rek?.model_size_mib || (gpu ? 4650 : 0)
  const kvCacheMib = Math.round((cfg?.num_ctx || 2048) * 0.075)
  const cudaBufferMib = Math.max(0, vramUsed - modelMib - kvCacheMib) || 300

  const modelWidthPercent = vramTotal > 0 ? Math.min(100, (modelMib / vramTotal) * 100) : 0
  const kvWidthPercent = vramTotal > 0 ? Math.min(100, (kvCacheMib / vramTotal) * 100) : 0
  const cudaWidthPercent = vramTotal > 0 ? Math.min(100, (cudaBufferMib / vramTotal) * 100) : 0

  if (loading && !data) {
    return (
      <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5">
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-2">
          <div className="skeleton h-6 w-56 rounded-md" />
          <div className="skeleton h-4 w-80 rounded-md" />
        </div>
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
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-20 relative">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef} className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>KESEHATAN MESIN AI</span>
            <InfoTooltip size="lg" content="Pemantauan perangkat keras, alokasi VRAM GPU, pemanfaatan RAM host, dan status eksekusi runtime inferensi model AI secara real-time." />
          </h1>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start md:self-auto">
          <Link
            to="/settings/chatbot"
            className="px-3.5 py-2 text-xs font-semibold rounded-xl text-[var(--text-secondary)] hover:text-sky-500 hover:bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Pengaturan</span>
          </Link>

          <button
            type="button"
            onClick={() => fetchDiagnostics(true)}
            disabled={refreshing}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] cursor-pointer disabled:opacity-50"
          >
            <svg
              className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{refreshing ? 'Memperbarui...' : 'Segarkan'}</span>
          </button>
        </div>
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

      {/* ── TABS NAVIGATION & DETAILS ───────────────────────────── */}
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

      {/* ── FOOTER STATUS ───────────────────────────────────────── */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] px-1">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span>
            {lastUpdated
              ? `Diperbarui: ${lastUpdated.toLocaleTimeString('id-ID')}`
              : 'Memeriksa...'}
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
