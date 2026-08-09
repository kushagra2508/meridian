import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAsyncData } from '../../hooks/useAsyncData'
import { getPersonaCatalog } from '../../lib/api'
import { formatTimestamp } from '../../lib/format'
import { findClosestPersona, formatTraitValue } from '../../lib/persona'
import type { Persona, PersonaProfile, PersonaTrait } from '../../lib/types'
import { Icon } from '../Icon'
import { Kicker } from '../Kicker'

interface PersonaSelectorProps {
  onPersonaChange: (persona: Persona | null) => void
  onContinue: () => void
}

export function PersonaSelector({ onPersonaChange, onContinue }: PersonaSelectorProps) {
  const catalogState = useAsyncData(useCallback((signal: AbortSignal) => getPersonaCatalog(signal), []))
  const catalog = catalogState.data

  const [profile, setProfile] = useState<PersonaProfile | null>(null)
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null)

  useEffect(() => {
    if (!catalog) return
    const fallback =
      catalog.personas.find((persona) => persona.id === catalog.defaultPersonaId) ??
      catalog.personas[0]
    setProfile(fallback ? { ...fallback.profile } : null)
    setFetchedAt(new Date())
  }, [catalog])

  const activePersona = useMemo(() => {
    if (!catalog || !profile) return null
    return findClosestPersona(catalog.personas, catalog.traits, profile)
  }, [catalog, profile])

  useEffect(() => {
    onPersonaChange(activePersona)
  }, [activePersona, onPersonaChange])

  const updateTrait = (trait: PersonaTrait, value: number) => {
    setProfile((previous) => (previous ? { ...previous, [trait.key]: value } : previous))
  }

  const resetToDefault = () => {
    if (!catalog) return
    const fallback =
      catalog.personas.find((persona) => persona.id === catalog.defaultPersonaId) ??
      catalog.personas[0]
    if (fallback) setProfile({ ...fallback.profile })
  }

  const allocationTotal = profile
    ? profile.equityAllocationPct + profile.depositAllocationPct
    : 0

  return (
    <section className="glass-panel mb-gutter rounded-xl p-gutter">
      <div className="mb-stack-lg flex flex-wrap items-start justify-between gap-4">
        <div>
          <Kicker className="mb-3">Meridian Wealth · Emerging Affluent</Kicker>
          <h2 className="font-page-title text-page-title tracking-tight text-on-surface">
            Who are we planning for?
          </h2>
          <p className="mt-2 max-w-2xl font-subtitle text-subtitle text-on-surface-variant">
            Choose a segment archetype, or dial in a profile and we will match it to the closest
            one.
          </p>
        </div>

        <div className="flex gap-1">
          <button
            type="button"
            onClick={resetToDefault}
            title="Reset to the default segment"
            className="rounded p-2 text-on-surface-variant transition-colors hover:bg-surface hover:text-primary"
          >
            <Icon name="restart_alt" className="text-[20px]" />
            <span className="sr-only">Reset to the default segment</span>
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            title="Print this view"
            className="rounded p-2 text-on-surface-variant transition-colors hover:bg-surface hover:text-primary"
          >
            <Icon name="print" className="text-[20px]" />
            <span className="sr-only">Print this view</span>
          </button>
        </div>
      </div>

      {catalogState.error ? (
        <p className="rounded border border-error/40 bg-error-container px-4 py-3 font-body text-body text-on-error-container">
          Could not load segment archetypes.
        </p>
      ) : null}

      {!catalog && !catalogState.error ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((slot) => (
            <div
              key={slot}
              className="h-56 animate-pulse rounded-lg border border-outline-variant bg-surface"
            />
          ))}
        </div>
      ) : null}

      {catalog && profile ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {catalog.personas.map((persona) => (
              <PersonaCard
                key={persona.id}
                persona={persona}
                active={persona.id === activePersona?.id}
                onSelect={() => setProfile({ ...persona.profile })}
              />
            ))}
          </div>

          <div className="mt-gutter rounded-lg border border-outline-variant border-l-[3px] border-l-primary bg-surface p-gutter">
            <h3 className="mb-stack-md font-panel-header text-panel-header text-on-surface">
              Build your own
            </h3>

            <div className="grid grid-cols-1 gap-x-12 gap-y-6 md:grid-cols-2">
              {catalog.traits.map((trait) => (
                <TraitSlider
                  key={trait.key}
                  trait={trait}
                  value={profile[trait.key]}
                  onChange={(value) => updateTrait(trait, value)}
                />
              ))}
            </div>

            {allocationTotal > 100 ? (
              <p className="mt-stack-md font-body text-body text-error">
                Equity and deposit allocations add up to {allocationTotal}% of investable assets.
              </p>
            ) : null}

            <div className="mt-stack-md inline-flex items-center gap-2 rounded border border-outline-variant bg-surface-container px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.08em] text-on-surface">
              <Icon name="target" className="text-[16px] text-primary" />
              Closest match: {activePersona ? `${activePersona.id} · ${activePersona.name}` : '—'}
            </div>
          </div>

          <div className="mt-gutter flex flex-wrap items-center justify-between gap-4 border-t border-outline-variant pt-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-on-surface-variant">
              Data fetched {fetchedAt ? formatTimestamp(fetchedAt) : '—'}
            </span>
            <button
              type="button"
              onClick={onContinue}
              className="flex items-center gap-2 rounded bg-primary px-6 py-3 font-body text-[11px] font-bold uppercase tracking-[0.15em] text-on-primary transition-opacity hover:opacity-90"
            >
              Continue
              <Icon name="chevron_right" className="text-[16px]" />
            </button>
          </div>
        </>
      ) : null}
    </section>
  )
}

interface PersonaCardProps {
  persona: Persona
  active: boolean
  onSelect: () => void
}

function PersonaCard({ persona, active, onSelect }: PersonaCardProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onSelect}
      className={`flex flex-col rounded-lg border-2 p-4 text-left transition-colors ${
        active
          ? 'border-primary bg-primary/5'
          : 'border-outline-variant bg-surface hover:border-primary/40'
      }`}
    >
      <div className="mb-4 flex w-full items-start justify-between gap-2">
        <span className="font-table-header text-table-header text-primary">{persona.id}</span>
        <span
          className={`rounded border px-2 py-0.5 font-table-header text-[9px] uppercase tracking-[0.08em] ${
            active
              ? 'border-primary bg-surface-container-lowest text-primary'
              : 'border-transparent bg-primary/10 text-primary'
          }`}
        >
          {persona.exhibit}
        </span>
      </div>

      <h3 className="font-panel-header text-panel-header text-on-surface">{persona.name}</h3>
      <p className="mt-2 font-body text-body text-on-surface-variant">{persona.thesis}</p>

      <dl className="mt-auto w-full space-y-2 pt-stack-md">
        <PersonaStat label="Income Band" value={persona.incomeBand} active={active} />
        <PersonaStat label="Self-Directed" value={`${persona.selfDirectedPct}%`} active={active} />
        <PersonaStat label="Pri. Channel" value={persona.primaryChannel} active={active} />
      </dl>
    </button>
  )
}

interface PersonaStatProps {
  label: string
  value: string
  active: boolean
}

function PersonaStat({ label, value, active }: PersonaStatProps) {
  return (
    <div
      className={`flex items-center justify-between gap-2 border-b pb-2 last:border-b-0 last:pb-0 ${
        active ? 'border-primary/20' : 'border-outline-variant'
      }`}
    >
      <dt className="font-table-header text-table-header uppercase tracking-[0.1em] text-on-surface-variant">
        {label}
      </dt>
      <dd className={`font-mono text-[11px] text-on-surface ${active ? 'font-bold' : ''}`}>
        {value}
      </dd>
    </div>
  )
}

interface TraitSliderProps {
  trait: PersonaTrait
  value: number
  onChange: (value: number) => void
}

function TraitSlider({ trait, value, onChange }: TraitSliderProps) {
  const filled = ((value - trait.min) / (trait.max - trait.min)) * 100

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="font-table-header text-table-header uppercase tracking-[0.1em] text-on-surface">
          {trait.label}
        </span>
        <span className="font-mono text-[11px] text-on-surface">
          {formatTraitValue(trait, value)}
        </span>
      </div>

      <div className="relative h-4">
        <input
          type="range"
          min={trait.min}
          max={trait.max}
          step={trait.step}
          value={value}
          aria-label={trait.label}
          onChange={(event) => onChange(Number(event.target.value))}
          className="peer absolute inset-0 z-10 w-full cursor-pointer opacity-0"
        />
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 bg-surface-container-high">
          <div className="h-full bg-primary" style={{ width: `${filled}%` }} />
        </div>
        <div
          className="pointer-events-none absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 bg-on-surface peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary"
          style={{ left: `${filled}%` }}
        />
      </div>
    </div>
  )
}
