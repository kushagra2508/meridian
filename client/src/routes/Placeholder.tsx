import { Icon } from '../components/Icon'
import { Kicker } from '../components/Kicker'

interface PlaceholderProps {
  title: string
  description: string
  icon: string
}

export function Placeholder({ title, description, icon }: PlaceholderProps) {
  return (
    <main className="z-10 flex-1 overflow-y-auto bg-background p-gutter pt-24">
      <div className="glass-panel flex min-h-[360px] flex-col items-start justify-center gap-stack-md rounded-xl p-margin">
        <Kicker>In Development</Kicker>
        <div className="flex items-center gap-3">
          <Icon name={icon} className="text-[32px] text-primary" />
          <h2 className="font-page-title text-page-title tracking-tight text-on-surface">
            {title}
          </h2>
        </div>
        <p className="max-w-xl font-subtitle text-subtitle text-on-surface-variant">
          {description}
        </p>
      </div>
    </main>
  )
}
