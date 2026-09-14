export function InfoTooltip({
  content,
  size = 'md',
  width,
  className = '',
  position, // 'top' | 'bottom' | 'right' | 'left'
  align = 'center', // 'left' | 'center' | 'right'
}) {
  if (!content) return null

  const sizeMap = {
    sm: {
      icon: 'w-3.5 h-3.5',
      card: 'p-2.5 text-xs leading-relaxed rounded-lg',
      defaultWidth: 'w-64',
    },
    md: {
      icon: 'w-4 h-4 sm:w-4.5 sm:h-4.5',
      card: 'p-3 text-xs leading-relaxed rounded-xl',
      defaultWidth: 'w-72 sm:w-80',
    },
    lg: {
      icon: 'w-5 h-5 sm:w-5.5 sm:h-5.5',
      card: 'p-3.5 sm:p-4 text-xs sm:text-sm leading-relaxed rounded-xl font-normal',
      defaultWidth: 'w-80 sm:w-96',
    },
  }

  const current = sizeMap[size] || sizeMap.md
  const popupWidth = width || current.defaultWidth

  // Smart default position: 'bottom' for large title headers to avoid top screen clipping
  const finalPosition = position || (size === 'lg' ? 'bottom' : 'top')

  let alignClasses = 'left-1/2 -translate-x-1/2'
  if (align === 'left') {
    alignClasses = 'left-0'
  } else if (align === 'right') {
    alignClasses = 'right-0'
  }

  let posClasses = `bottom-full ${alignClasses} mb-2.5`
  if (finalPosition === 'bottom') {
    posClasses = `top-full ${alignClasses} mt-2.5`
  } else if (finalPosition === 'right') {
    posClasses = 'left-full top-1/2 -translate-y-1/2 ml-2.5'
  } else if (finalPosition === 'left') {
    posClasses = 'right-full top-1/2 -translate-y-1/2 mr-2.5'
  }

  return (
    <span
      className={`relative group inline-flex items-center align-middle cursor-help ml-2 shrink-0 z-10 group-hover:z-[9999] hover:z-[9999] ${className}`}
    >
      <svg
        className={`${current.icon} text-[var(--text-muted)] group-hover:text-sky-500 transition-all duration-200 shrink-0 group-hover:scale-110`}
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
      <span
        className={`pointer-events-none absolute ${posClasses} opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-[9999] ${current.card} bg-white dark:bg-[#1a1b1e] text-[var(--text-primary)] border border-[var(--border-color)] normal-case text-left max-w-[85vw] ${popupWidth}`}
        style={{
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
        }}
      >
        {content}
      </span>
    </span>
  )
}

export default InfoTooltip
