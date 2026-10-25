import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { mesinApi } from "../../api/mesin";
import { addAppNotification } from "../../utils/notifications";
import gsap from "gsap";

/** Pengambilan diagnostik, refresh/visibility, animasi kartu, serta metrik runtime mesin. */
export function useHardwareMonitoring() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [activeTab, setActiveTab] = useState('hardware')

  // 'hardware' | 'ollama' | 'config'
  const [autoRefresh, setAutoRefresh] = useState(true)
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
      if (!document.hidden) {
        fetchDiagnostics(false)
      }
    }, 15000)

    const handleVisibilityChange = () => {
      if (!document.hidden) {
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
  const isLoaded = Boolean(oll?.termuat)
  const isFullGpu = isLoaded && (oll?.persen_di_gpu ?? 0) >= 99
  const vramTotal = gpu?.vram_total_mib || 0
  const vramUsed = gpu?.vram_dipakai_mib || 0
  const vramFree = gpu?.vram_bebas_mib || 0
  const vramPercent = vramTotal > 0 ? Math.min(100, Math.round((vramUsed / vramTotal) * 100)) : 0
  const ramTotal = ram?.ram_total_mib || 0
  const ramUsed = ram?.ram_dipakai_mib || 0
  const ramFree = ram?.ram_bebas_mib || 0
  const ramPercent = ramTotal > 0 ? Math.min(100, Math.round((ramUsed / ramTotal) * 100)) : 0
  const modelMib = oll?.di_gpu_mib || rek?.model_size_mib || (gpu ? 4650 : 0)
  const kvCacheMib = Math.round((cfg?.num_ctx || 2048) * 0.075)
  const cudaBufferMib = Math.max(0, vramUsed - modelMib - kvCacheMib) || 300
  const modelWidthPercent = vramTotal > 0 ? Math.min(100, (modelMib / vramTotal) * 100) : 0
  const kvWidthPercent = vramTotal > 0 ? Math.min(100, (kvCacheMib / vramTotal) * 100) : 0
  const cudaWidthPercent = vramTotal > 0 ? Math.min(100, (cudaBufferMib / vramTotal) * 100) : 0

  return {
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
  };
}
