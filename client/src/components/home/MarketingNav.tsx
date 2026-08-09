import { Link } from 'react-router-dom'
import { Icon } from '../Icon'

const links = ['Platform', 'Insights', 'Security']

export function MarketingNav() {
  return (
    <nav className="fixed left-0 top-0 z-50 flex h-20 w-full items-center justify-between border-b border-outline-variant/50 bg-background/90 px-gutter backdrop-blur-md md:px-margin">
      <Link to="/" className="flex items-center gap-3">
        <Icon name="token" className="text-3xl text-primary-container" filled />
        <span className="font-panel-header text-panel-header tracking-tight text-on-surface">
          Lumina
        </span>
      </Link>

      <div className="hidden items-center gap-8 md:flex">
        {links.map((link) => (
          <a
            key={link}
            href="#platform"
            className="font-section-kicker text-[11px] uppercase tracking-wider text-on-surface-variant transition-colors hover:text-primary-container"
          >
            {link}
          </a>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <Link
          to="/dashboard"
          className="hidden px-4 py-2 font-section-kicker text-[11px] uppercase tracking-wider text-on-surface-variant transition-colors hover:text-primary-container md:block"
        >
          Sign In
        </Link>
        <Link
          to="/dashboard"
          className="rounded-full bg-primary-container px-6 py-3 font-section-kicker text-[11px] uppercase tracking-wider text-on-primary transition-colors hover:bg-primary"
        >
          Get Started
        </Link>
      </div>
    </nav>
  )
}
