export interface NavItem {
  to: string
  label: string
  icon: string
}

export const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Overview', icon: 'dashboard' },
  { to: '/portfolio', label: 'Portfolio', icon: 'account_balance_wallet' },
  { to: '/intelligence', label: 'Intelligence', icon: 'psychology' },
  { to: '/reports', label: 'Reports', icon: 'assessment' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]
