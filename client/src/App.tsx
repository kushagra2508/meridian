import { CommitteeStep } from './components/edge/CommitteeStep'
import { EdgeChrome } from './components/edge/EdgeChrome'
import { EligibilityStep } from './components/edge/EligibilityStep'
import { GlossaryStep } from './components/edge/GlossaryStep'
import { GoalStep } from './components/edge/GoalStep'
import { HandoffStep } from './components/edge/HandoffStep'
import { PositionStep } from './components/edge/PositionStep'
import { VerdictStep } from './components/edge/VerdictStep'
import { hasChrome } from './edge/flow'
import { EdgeProvider, useEdgeState } from './edge/store'
import type { EdgeScreen } from './edge/types'

/** Transactional screens sit alone on the page at their own document width. */
const BARE_WIDTH: Partial<Record<EdgeScreen, string>> = {
  handoff: 'max-w-[780px]',
  goal: 'max-w-[720px]',
  eligibility: 'max-w-[1440px]',
}

function CurrentScreen({ screen }: { screen: EdgeScreen }) {
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
    case 'glossary':
      return <GlossaryStep />
    default:
      return null
  }
}

function EdgeFlow() {
  const { screen } = useEdgeState()
  const body = <CurrentScreen screen={screen} />

  if (hasChrome(screen)) {
    return <EdgeChrome>{body}</EdgeChrome>
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-8 font-body-md text-on-background antialiased">
      <div className={`w-full ${BARE_WIDTH[screen] ?? 'max-w-[780px]'}`}>{body}</div>
    </div>
  )
}

export default function App() {
  return (
    <EdgeProvider>
      <EdgeFlow />
    </EdgeProvider>
  )
}
