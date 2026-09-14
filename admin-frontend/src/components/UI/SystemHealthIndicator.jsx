import { useState, useEffect, useRef } from 'react'
import gsap from 'gsap'

export function SystemHealthIndicator({ isSidebar = false, isCollapsed = false }) {
  const [healthData, setHealthData] = useState(null)
  const [status, setStatus] = useState('loading') // 'healthy' | 'degraded' | 'offline' | 'loading'
  const [isOpen, setIsOpen] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const dropdownRef = useRef(null)
  const containerRef = useRef(null)
  const isClosingRef = useRef(false)

  const checkHealth = async () => {
    setIsRefreshing(true)
    try {
      const res = await fetch('/api/ai/health', {
        headers: { Accept: 'application/json' },
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = await res.json()
      setHealthData(data)
      setStatus(data.status || (allChecksOk(data.checks) ? 'healthy' : 'degraded'))
    } catch (err) {
      setStatus('offline')
      setHealthData({
        status: 'offline',
        service: 'ai-service',
        model: 'Tidak terhubung',
        checks: {
          chromadb: { ok: false, detail: 'Off' },
          ollama: { ok: false, detail: 'Off' },
          mysql: { ok: false, detail: 'Off' },
          redis: { ok: false, detail: 'Off' },
        },
      })
    } finally {
      setIsRefreshing(false)
    }
  }

  function allChecksOk(checks) {
    if (!checks) return false
    return Object.values(checks).every((c) => c && c.ok)
  }

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown on outside click or Escape
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (
        isOpen &&
        containerRef.current &&
        !containerRef.current.contains(e.target)
      ) {
        closeDropdown()
      }
    }
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        closeDropdown()
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const openDropdown = () => {
    setIsOpen(true)
    isClosingRef.current = false
    setTimeout(() => {
      if (dropdownRef.current) {
        gsap.fromTo(
          dropdownRef.current,
          { opacity: 0, scale: 0.95, y: 6 },
          { opacity: 1, scale: 1, y: 0, duration: 0.18, ease: 'power2.out' }
        )
      }
    }, 10)
  }

  const closeDropdown = () => {
    if (isClosingRef.current) return
    if (dropdownRef.current) {
      isClosingRef.current = true
      gsap.to(dropdownRef.current, {
        opacity: 0,
        scale: 0.95,
        y: 6,
        duration: 0.14,
        ease: 'power2.in',
        onComplete: () => {
          setIsOpen(false)
          isClosingRef.current = false
        },
      })
    } else {
      setIsOpen(false)
    }
  }

  const toggleDropdown = () => {
    if (isOpen) {
      closeDropdown()
    } else {
      openDropdown()
    }
  }

  const vectorCount = healthData?.checks?.chromadb?.detail || '0 vektor'
  const modelName = healthData?.model || healthData?.checks?.ollama?.detail || 'qwen3:8b'

  const isFastApiOk = status !== 'offline'
  const isOllamaOk = Boolean(healthData?.checks?.ollama?.ok)
  const isChromaOk = Boolean(healthData?.checks?.chromadb?.ok)
  const isDbOk = Boolean(healthData?.checks?.mysql?.ok && healthData?.checks?.redis?.ok)

  // Hitung jumlah service yang aktif (0 - 4)
  const activeCount = [isFastApiOk, isOllamaOk, isChromaOk, isDbOk].filter(Boolean).length
  const isAllHealthy = activeCount === 4

  return (
    <div className={`relative ${isSidebar ? 'w-full' : ''}`} ref={containerRef}>
      {/* Trigger Button: Cukup Teks dan Angka Murni */}
      {isSidebar ? (
        isCollapsed ? (
          <button
            type="button"
            onClick={toggleDropdown}
            className={`w-full py-1 text-center font-mono font-black text-xs cursor-pointer select-none bg-transparent border-0 outline-none hover:opacity-80 transition-opacity ${
              isAllHealthy ? 'text-emerald-500' : 'text-rose-500'
            }`}
            title={`Status Layanan AI (${activeCount}/4)`}
          >
            {activeCount}/4
          </button>
        ) : (
          <button
            type="button"
            onClick={toggleDropdown}
            className="w-full flex items-center justify-between py-1 text-xs cursor-pointer select-none group bg-transparent border-0 outline-none hover:opacity-80 transition-opacity"
            title="Klik untuk melihat rincian subsistem AI"
          >
            <span className="font-semibold text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] text-xs">
              Layanan AI
            </span>
            <span
              className={`font-mono font-black text-xs ${
                isAllHealthy ? 'text-emerald-500' : 'text-rose-500'
              }`}
            >
              {activeCount}/4
            </span>
          </button>
        )
      ) : (
        <button
          type="button"
          onClick={toggleDropdown}
          className={`font-mono font-black text-xs bg-transparent border-0 cursor-pointer ${
            isAllHealthy ? 'text-emerald-500' : 'text-rose-500'
          }`}
        >
          {activeCount}/4
        </button>
      )}

      {/* Popover Rincian Subsistem */}
      {isOpen && (
        <div
          ref={dropdownRef}
          className={`absolute ${
            isSidebar
              ? 'bottom-full mb-2.5 left-0 w-80 sm:w-88'
              : 'right-0 mt-2 w-80 sm:w-88'
          } bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-2xl z-[100] overflow-hidden text-xs`}
        >
          {/* Header */}
          <div className="px-4 py-3 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-input)]">
            <div className="flex items-center gap-2">
              <span className="font-bold text-xs text-[var(--text-primary)]">
                Status Subsistem AI
              </span>
              <span
                className={`font-mono font-black text-xs ${
                  isAllHealthy ? 'text-emerald-500' : 'text-rose-500'
                }`}
              >
                {activeCount}/4
              </span>
            </div>
            <button
              type="button"
              onClick={checkHealth}
              disabled={isRefreshing}
              className="text-xs font-semibold text-sky-500 hover:text-sky-600 disabled:opacity-50 cursor-pointer flex items-center gap-1"
            >
              {isRefreshing ? 'Memeriksa...' : 'Segarkan'}
            </button>
          </div>

          {/* Clean 4-Row List */}
          <div className="divide-y divide-[var(--border-color)] text-xs">
            {/* 1. FastAPI AI Microservice */}
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold text-xs text-[var(--text-primary)] leading-tight m-0">
                  AI Microservice
                </p>
                <p className="text-[11px] text-[var(--text-muted)] font-mono leading-tight mt-0.5 m-0">
                  FastAPI Gateway • Port 8080
                </p>
              </div>
              <span
                className={`text-xs font-bold font-mono shrink-0 ${
                  isFastApiOk ? 'text-emerald-500' : 'text-rose-500'
                }`}
              >
                {isFastApiOk ? 'Aktif' : 'Terputus'}
              </span>
            </div>

            {/* 2. Ollama LLM Engine */}
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold text-xs text-[var(--text-primary)] leading-tight m-0">
                  Model Bahasa (LLM)
                </p>
                <p className="text-[11px] text-[var(--text-muted)] font-mono leading-tight mt-0.5 m-0 truncate">
                  Ollama Engine • {modelName}
                </p>
              </div>
              <span
                className={`text-xs font-bold font-mono shrink-0 ${
                  isOllamaOk ? 'text-emerald-500' : 'text-rose-500'
                }`}
              >
                {isOllamaOk ? 'Terhubung' : 'Galat'}
              </span>
            </div>

            {/* 3. ChromaDB Vector Store */}
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold text-xs text-[var(--text-primary)] leading-tight m-0">
                  Basis Vektor Dokumen
                </p>
                <p className="text-[11px] text-[var(--text-muted)] font-mono leading-tight mt-0.5 m-0">
                  ChromaDB Store • Semantik BGE-M3
                </p>
              </div>
              <span
                className={`text-xs font-bold font-mono shrink-0 ${
                  isChromaOk ? 'text-sky-500' : 'text-rose-500'
                }`}
              >
                {isChromaOk ? vectorCount : 'Galat'}
              </span>
            </div>

            {/* 4. MySQL & Redis */}
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold text-xs text-[var(--text-primary)] leading-tight m-0">
                  Database & Antrean
                </p>
                <p className="text-[11px] text-[var(--text-muted)] font-mono leading-tight mt-0.5 m-0">
                  MySQL Database & Redis Worker
                </p>
              </div>
              <span
                className={`text-xs font-bold font-mono shrink-0 ${
                  isDbOk ? 'text-emerald-500' : 'text-rose-500'
                }`}
              >
                {isDbOk ? 'Normal' : 'Terputus'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SystemHealthIndicator
