import { useEffect, useState } from 'react'

const RADIUS = 45
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

interface HealthGaugeProps {
  score: number
}

export function HealthGauge({ score }: HealthGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setAnimatedScore(score))
    return () => cancelAnimationFrame(frame)
  }, [score])

  const offset = CIRCUMFERENCE * (1 - animatedScore / 100)

  return (
    <div className="relative flex flex-1 flex-col items-center justify-center">
      <svg
        className="h-48 w-48 -rotate-90"
        viewBox="0 0 100 100"
        role="img"
        aria-label={`Portfolio health score ${score} out of 100`}
      >
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="#eae7e7"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="#006d35"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-page-title text-page-title leading-none text-secondary">
          {score}
        </span>
        <span className="mt-1 font-section-kicker text-section-kicker uppercase text-on-surface-variant">
          Score
        </span>
      </div>
    </div>
  )
}
