import { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'

export function InfoTooltip({
  content,
  size = 'md',
  width,
  className = '',
  position, // 'top' | 'bottom' | 'right' | 'left'
  align = 'center', // 'left' | 'center' | 'right'
}) {
  if (!content) return null

  const [isOpen, setIsOpen] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0, placement: 'top', arrowLeft: 0 })
  const triggerRef = useRef(null)
  const tooltipRef = useRef(null)
  const timeoutRef = useRef(null)

  const sizeMap = {
    sm: {
      icon: 'w-3.5 h-3.5',
      card: 'p-2.5 text-xs leading-relaxed rounded-lg',
      widthNum: 256,
      defaultWidth: 'w-64',
    },
    md: {
      icon: 'w-4 h-4 sm:w-4.5 sm:h-4.5',
      card: 'p-3 text-xs leading-relaxed rounded-xl',
      widthNum: 300,
      defaultWidth: 'w-72 sm:w-80',
    },
    lg: {
      icon: 'w-5 h-5 sm:w-5.5 sm:h-5.5',
      card: 'p-3.5 sm:p-4 text-xs sm:text-sm leading-relaxed rounded-xl font-normal',
      widthNum: 360,
      defaultWidth: 'w-80 sm:w-96',
    },
  }

  const current = sizeMap[size] || sizeMap.md

  const updatePosition = () => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const tooltipEl = tooltipRef.current

    const tooltipWidth = tooltipEl ? tooltipEl.offsetWidth : (width ? parseInt(width, 10) || current.widthNum : current.widthNum)
    const tooltipHeight = tooltipEl ? tooltipEl.offsetHeight : 80
    const margin = 8

    let targetPlacement = position || (size === 'lg' ? 'bottom' : 'top')

    // Smart auto-flip if clipping top or bottom viewport
    if (targetPlacement === 'top' && rect.top - tooltipHeight - margin < 10) {
      targetPlacement = 'bottom'
    } else if (targetPlacement === 'bottom' && rect.bottom + tooltipHeight + margin > window.innerHeight - 10) {
      targetPlacement = 'top'
    }

    let top = 0
    let left = 0

    if (targetPlacement === 'top') {
      top = rect.top - tooltipHeight - margin
    } else if (targetPlacement === 'bottom') {
      top = rect.bottom + margin
    } else if (targetPlacement === 'right') {
      top = rect.top + rect.height / 2 - tooltipHeight / 2
      left = rect.right + margin
    } else if (targetPlacement === 'left') {
      top = rect.top + rect.height / 2 - tooltipHeight / 2
      left = rect.left - tooltipWidth - margin
    }

    if (targetPlacement === 'top' || targetPlacement === 'bottom') {
      if (align === 'left') {
        left = rect.left
      } else if (align === 'right') {
        left = rect.right - tooltipWidth
      } else {
        left = rect.left + rect.width / 2 - tooltipWidth / 2
      }
    }

    // Viewport collision clamping
    const minLeft = 12
    const maxLeft = Math.max(12, window.innerWidth - tooltipWidth - 12)
    const clampedLeft = Math.min(Math.max(left, minLeft), maxLeft)
    const clampedTop = Math.max(8, Math.min(top, window.innerHeight - tooltipHeight - 8))

    // Calculate arrow offset relative to trigger center
    const triggerCenter = rect.left + rect.width / 2
    const arrowLeft = Math.max(12, Math.min(triggerCenter - clampedLeft, tooltipWidth - 12))

    setCoords({
      top: clampedTop,
      left: clampedLeft,
      placement: targetPlacement,
      arrowLeft,
    })
  }

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    updatePosition()
    setIsOpen(true)
  }

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setIsOpen(false)
    }, 100)
  }

  useLayoutEffect(() => {
    if (isOpen) {
      updatePosition()
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return

    const handleScrollOrResize = () => {
      updatePosition()
    }

    window.addEventListener('scroll', handleScrollOrResize, true)
    window.addEventListener('resize', handleScrollOrResize)

    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true)
      window.removeEventListener('resize', handleScrollOrResize)
    }
  }, [isOpen])

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={`inline-flex items-center align-middle cursor-help ml-2 shrink-0 select-none ${className}`}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <svg
          className={`${current.icon} text-[var(--text-muted)] hover:text-sky-500 transition-colors duration-150 shrink-0`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </span>

      {isOpen &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            ref={tooltipRef}
            onMouseEnter={() => {
              if (timeoutRef.current) clearTimeout(timeoutRef.current)
            }}
            onMouseLeave={handleMouseLeave}
            style={{
              position: 'fixed',
              top: `${coords.top}px`,
              left: `${coords.left}px`,
              zIndex: 999999,
              boxShadow:
                '0 20px 25px -5px rgba(0, 0, 0, 0.35), 0 8px 10px -6px rgba(0, 0, 0, 0.25)',
            }}
            className={`pointer-events-auto transition-opacity duration-150 animate-in fade-in zoom-in-95 ${current.card} bg-white dark:bg-[#1a1b1e] text-[var(--text-primary)] border border-[var(--border-color)] normal-case text-left max-w-[90vw] ${
              width || current.defaultWidth
            }`}
          >
            {content}
          </div>,
          document.body
        )}
    </>
  )
}

export default InfoTooltip
