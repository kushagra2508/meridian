import { formatWholeCurrency } from './format'
import type { Persona, PersonaProfile, PersonaTrait } from './types'

export function formatTraitValue(trait: PersonaTrait, value: number): string {
  switch (trait.unit) {
    case 'years':
      return `${value} YRS`
    case 'currency':
      return formatWholeCurrency(value)
    case 'percent':
      return `${value}%`
  }
}

/**
 * Euclidean distance over traits normalised to their own slider span, so a
 * $50k salary gap does not swamp a 20-point allocation gap.
 */
function distance(profile: PersonaProfile, persona: Persona, traits: PersonaTrait[]): number {
  return traits.reduce((total, trait) => {
    const span = trait.max - trait.min || 1
    const delta = (profile[trait.key] - persona.profile[trait.key]) / span
    return total + delta * delta
  }, 0)
}

export function findClosestPersona(
  personas: Persona[],
  traits: PersonaTrait[],
  profile: PersonaProfile,
): Persona | null {
  let closest: Persona | null = null
  let smallest = Number.POSITIVE_INFINITY

  for (const persona of personas) {
    const score = distance(profile, persona, traits)
    if (score < smallest) {
      smallest = score
      closest = persona
    }
  }

  return closest
}
