import { Icon } from './Icon'

interface TopAppBarProps {
  onOpenNav: () => void
}

export function TopAppBar({ onOpenNav }: TopAppBarProps) {
  return (
    <header className="fixed right-0 top-0 z-30 flex h-16 w-full items-center justify-between border-b border-outline-variant bg-surface px-gutter md:w-[calc(100%-16rem)]">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          className="text-on-surface-variant transition-colors hover:text-primary md:hidden"
        >
          <Icon name="menu" />
        </button>
        <span className="font-panel-header text-panel-header uppercase tracking-widest text-primary md:hidden">
          Lumina
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center rounded-full border border-outline-variant bg-surface-container px-4 py-1.5 transition-all focus-within:border-primary md:flex">
          <Icon name="search" className="mr-2 text-[20px] text-on-surface-variant" />
          <input
            type="search"
            placeholder="Search assets..."
            aria-label="Search assets"
            className="w-48 border-none bg-transparent text-body text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-0"
          />
        </div>

        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Notifications"
            className="relative p-2 text-on-surface-variant transition-colors hover:text-primary active:scale-90"
          >
            <Icon name="notifications" />
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-error" />
          </button>
          <button
            type="button"
            aria-label="Help"
            className="p-2 text-on-surface-variant transition-colors hover:text-primary active:scale-90"
          >
            <Icon name="help_outline" />
          </button>
          <button
            type="button"
            aria-label="Account"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-outline-variant bg-surface-container-high text-on-surface-variant transition-colors hover:text-primary"
          >
            <Icon name="person" className="text-[20px]" />
          </button>
        </div>
      </div>
    </header>
  )
}
