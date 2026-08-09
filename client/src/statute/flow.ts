import type { StatuteScreen } from './types'

export type FlowStep = {
  id: StatuteScreen
  label: string
  icon: string
}

export const FLOW_STEPS: FlowStep[] = [
  { id: 'handoff', label: 'Handoff', icon: 'move_to_inbox' },
  { id: 'position', label: 'Position', icon: 'tune' },
  { id: 'goal', label: 'Goal', icon: 'flag' },
  { id: 'eligibility', label: 'Shelf', icon: 'shelves' },
  { id: 'committee', label: 'Deliberation', icon: 'gavel' },
  { id: 'verdict', label: 'Verdict', icon: 'list_alt' },
]

/**
 * Handoff, Goal and Shelf are transactional: they suppress the navigation
 * shell so the document sits alone on the page.
 */
const CHROME_SCREENS: StatuteScreen[] = ['position', 'committee', 'verdict']

export function hasChrome(screen: StatuteScreen): boolean {
  return CHROME_SCREENS.includes(screen)
}

export function stepIndex(screen: StatuteScreen): number {
  return Math.max(
    0,
    FLOW_STEPS.findIndex((s) => s.id === screen),
  )
}

export function nextScreen(screen: StatuteScreen): StatuteScreen | null {
  const idx = FLOW_STEPS.findIndex((s) => s.id === screen)
  if (idx < 0 || idx >= FLOW_STEPS.length - 1) return null
  return FLOW_STEPS[idx + 1]!.id
}
