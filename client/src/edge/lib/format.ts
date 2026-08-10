const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const inrCompact = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 0,
})

export function formatINR(value: number): string {
  return inr.format(Math.round(value))
}

export function formatINRPlain(value: number): string {
  return `₹${inrCompact.format(Math.round(value))}`
}

export function formatPct(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`
}

export function parseINRInput(raw: string): number {
  const digits = raw.replace(/[^\d]/g, '')
  return digits ? Number(digits) : 0
}
