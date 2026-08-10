/**
 * The relationship manager working this desk. There is no auth/session layer
 * yet, so this stands in for whoever is logged in — swap for the session
 * user once identity exists.
 */
export const CURRENT_RM = {
  name: 'Priya Nair',
  desk: 'Mumbai Private Wealth',
}

export function greeting(date = new Date()): string {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}
