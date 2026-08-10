import type { EdgeScreen } from './types'

export type FlowStep = {
  id: EdgeScreen
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
 * shell so the document sits alone on the page. Glossary sits in the chrome
 * as a side door, not a flow step.
 */
const CHROME_SCREENS: EdgeScreen[] = ['position', 'committee', 'verdict', 'glossary']

export function hasChrome(screen: EdgeScreen): boolean {
  return CHROME_SCREENS.includes(screen)
}

export function stepIndex(screen: EdgeScreen): number {
  return FLOW_STEPS.findIndex((s) => s.id === screen)
}

export function nextScreen(screen: EdgeScreen): EdgeScreen | null {
  const idx = FLOW_STEPS.findIndex((s) => s.id === screen)
  if (idx < 0 || idx >= FLOW_STEPS.length - 1) return null
  return FLOW_STEPS[idx + 1]!.id
}
