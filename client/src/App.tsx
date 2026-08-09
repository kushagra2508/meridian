import { CommitteeStep } from './components/statute/CommitteeStep'
import { EligibilityStep } from './components/statute/EligibilityStep'
import { GoalStep } from './components/statute/GoalStep'
import { HandoffStep } from './components/statute/HandoffStep'
import { PositionStep } from './components/statute/PositionStep'
import { StatuteChrome } from './components/statute/StatuteChrome'
import { VerdictStep } from './components/statute/VerdictStep'
import { hasChrome } from './statute/flow'
import { StatuteProvider, useStatuteState } from './statute/store'
import type { StatuteScreen } from './statute/types'

/** Transactional screens sit alone on the page at their own document width. */
const BARE_WIDTH: Partial<Record<StatuteScreen, string>> = {
  handoff: 'max-w-[780px]',
  goal: 'max-w-[720px]',
  eligibility: 'max-w-[1440px]',
}

function CurrentScreen({ screen }: { screen: StatuteScreen }) {
  switch (screen) {
    case 'handoff':
      return <HandoffStep />
    case 'position':
      return <PositionStep />
    case 'goal':
      return <GoalStep />
    case 'eligibility':
      return <EligibilityStep />
    case 'committee':
      return <CommitteeStep />
    case 'verdict':
      return <VerdictStep />
    default:
      return null
  }
}

function StatuteFlow() {
  const { screen } = useStatuteState()
  const body = <CurrentScreen screen={screen} />

  if (hasChrome(screen)) {
    return <StatuteChrome>{body}</StatuteChrome>
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-8 font-body-md text-on-background antialiased">
      <div className={`w-full ${BARE_WIDTH[screen] ?? 'max-w-[780px]'}`}>{body}</div>
    </div>
  )
}

export default function App() {
  return (
    <StatuteProvider>
      <StatuteFlow />
    </StatuteProvider>
  )
}
