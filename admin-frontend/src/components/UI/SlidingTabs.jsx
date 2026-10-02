import React, { useRef, useLayoutEffect, useEffect } from 'react'
import gsap from 'gsap'

/**
 * SlidingTabs - Smooth GSAP-powered sliding pill & underline highlight tab component
 * Replicates the fluid sidebar highlight physics across any button group or tab switcher.
 */
export function SlidingTabs({
  tabs = [],
  activeTab,
  onChange,
  variant = 'pill', // 'pill' | 'underline'
  className = '',
  pillClassName = '',
  fullWidth = false,
  size = 'sm',
}) {
  const containerRef = useRef(null)
  const pillRef = useRef(null)
  const tabRefs = useRef({})
  const isInitialMount = useRef(true)

  const updatePillPosition = (animate = true) => {
    const targetEl = tabRefs.current[activeTab]
    if (!targetEl || !pillRef.current) return

    const left = targetEl.offsetLeft
    const top = targetEl.offsetTop
    const width = targetEl.offsetWidth
    const height = targetEl.offsetHeight

    if (animate && !isInitialMount.current) {
      gsap.killTweensOf(pillRef.current)
      if (variant === 'underline') {
        gsap.to(pillRef.current, {
          left,
          width,
          opacity: 1,
          duration: 0.35,
          ease: 'power3.out',
        })
      } else {
        gsap.to(pillRef.current, {
          left,
          top,
          width,
          height,
          opacity: 1,
          duration: 0.35,
          ease: 'power3.out',
        })
      }
    } else {
      if (variant === 'underline') {
        gsap.set(pillRef.current, { left, width, opacity: 1 })
      } else {
        gsap.set(pillRef.current, { left, top, width, height, opacity: 1 })
      }
      isInitialMount.current = false
    }
  }

  useLayoutEffect(() => {
    updatePillPosition(true)
  }, [activeTab, tabs])

  useEffect(() => {
    const handleResize = () => updatePillPosition(false)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [activeTab])

  if (variant === 'underline') {
    return (
      <div
        ref={containerRef}
        className={`relative flex gap-4 sm:gap-6 border-b border-[var(--border-color)] overflow-x-auto scrollbar-none flex-nowrap ${className}`}
      >
        {/* Smooth GSAP Sliding Underline */}
        <div
          ref={pillRef}
          className={`absolute bottom-0 h-0.5 bg-sky-500 rounded-full pointer-events-none z-0 ${pillClassName}`}
          style={{ opacity: 0 }}
        />

        {tabs.map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              ref={(el) => {
                if (el) tabRefs.current[tab.id] = el
              }}
              type="button"
              onClick={() => onChange(tab.id)}
              className={`pb-3 text-xs transition-colors cursor-pointer relative z-10 whitespace-nowrap shrink-0 ${
                isActive
                  ? 'text-sky-500 font-bold'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] font-semibold'
              }`}
            >
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>
    )
  }

  // Default: Pill Variant
  return (
    <div
      ref={containerRef}
      className={`relative ${
        fullWidth ? 'w-full flex justify-between' : 'inline-flex'
      } items-center gap-1 bg-[var(--bg-card)] p-1 rounded-xl border border-[var(--border-color)] select-none overflow-x-auto scrollbar-none flex-nowrap max-w-full ${className}`}
    >
      {/* Smooth GSAP Sliding Pill */}
      <div
        ref={pillRef}
        className={`absolute rounded-lg bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 shadow-md shadow-sky-500/25 pointer-events-none z-0 ${pillClassName}`}
        style={{ opacity: 0 }}
      />

      {tabs.map((tab) => {
        const isActive = activeTab === tab.id
        return (
          <button
            key={tab.id}
            ref={(el) => {
              if (el) tabRefs.current[tab.id] = el
            }}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`relative z-10 rounded-lg font-bold transition-colors duration-200 cursor-pointer text-center whitespace-nowrap ${
              fullWidth ? 'flex-1' : 'shrink-0'
            } ${
              size === 'lg'
                ? 'px-5 py-2.5 text-sm sm:text-base'
                : size === 'md'
                  ? 'px-4 sm:px-5 py-2 text-xs sm:text-sm'
                  : size === 'xs'
                    ? 'px-2.5 py-1 text-xs font-mono uppercase'
                    : 'px-3.5 py-1.5 text-xs'
            } ${
              isActive
                ? 'text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
