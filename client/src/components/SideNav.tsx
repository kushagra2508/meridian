import { NavLink } from 'react-router-dom'
import { Icon } from './Icon'
import { navItems } from './navItems'

interface SideNavProps {
  open: boolean
  onNavigate: () => void
}

export function SideNav({ open, onNavigate }: SideNavProps) {
  return (
    <>
      {open ? (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={onNavigate}
          className="fixed inset-0 z-40 bg-inverse-surface/40 md:hidden"
        />
      ) : null}

      <nav
        className={`fixed left-0 top-0 z-50 flex h-full w-64 flex-col border-r border-outline-variant bg-background py-stack-lg transition-transform duration-200 md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mb-stack-lg flex items-center gap-3 px-gutter">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-outline-variant bg-primary text-on-primary">
            <Icon name="token" className="text-[22px]" filled />
          </div>
          <div>
            <h1 className="font-panel-header text-panel-header uppercase leading-none tracking-widest text-primary">
              Lumina
            </h1>
            <span className="mt-1 block font-footnote text-footnote uppercase tracking-wider text-on-surface-variant">
              Private Banking
            </span>
          </div>
        </div>

        <ul className="flex-1 space-y-1">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-gutter py-3 transition-colors duration-200 ${
                    isActive
                      ? 'border-r-4 border-primary bg-surface-container-low font-bold text-primary'
                      : 'text-on-surface-variant hover:bg-surface-container-high hover:text-primary'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon name={item.icon} filled={isActive} />
                    <span className="text-body">{item.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        <div className="mt-auto px-gutter">
          <button
            type="button"
            className="w-full rounded bg-primary py-3 font-bold text-on-primary transition-opacity hover:opacity-90"
          >
            Contact Advisor
          </button>
        </div>
      </nav>
    </>
  )
}
