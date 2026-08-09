interface IconProps {
  name: string
  className?: string
  filled?: boolean
}

export function Icon({ name, className = '', filled = false }: IconProps) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined${filled ? ' filled' : ''} ${className}`.trim()}
    >
      {name}
    </span>
  )
}
