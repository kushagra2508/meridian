interface KickerProps {
  children: React.ReactNode
  className?: string
}

export function Kicker({ children, className = '' }: KickerProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`.trim()}>
      <div className="h-[3px] w-4 bg-primary-container" />
      <span className="font-section-kicker text-[11px] uppercase tracking-[0.1em] text-primary-container">
        {children}
      </span>
    </div>
  )
}
