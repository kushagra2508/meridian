import { Link } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { Kicker } from '../components/Kicker'
import { MarketingNav } from '../components/home/MarketingNav'
import { RebalancingPanel } from '../components/home/RebalancingPanel'

export function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-on-surface">
      <MarketingNav />

      <main className="flex-grow pt-20">
        <section className="relative flex min-h-[80vh] items-center justify-center overflow-hidden px-gutter py-24 md:px-margin">
          <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_20%_20%,rgba(25,122,86,0.10),transparent_55%),radial-gradient(circle_at_80%_30%,rgba(80,253,145,0.12),transparent_50%)]" />
          <div className="pointer-events-none absolute inset-0 z-0 bg-gradient-to-b from-transparent via-background/80 to-background" />

          <div className="relative z-10 mx-auto flex w-full max-w-container-max flex-col items-start gap-stack-lg">
            <Kicker>AI Engine Online</Kicker>

            <h1 className="max-w-4xl font-page-title text-page-title font-bold tracking-tight text-on-surface md:text-[56px] md:leading-[1.1]">
              Your Wealth, <br className="hidden md:block" />
              <span className="text-primary-container">Intelligence-Driven.</span>
            </h1>

            <p className="max-w-2xl font-subtitle text-subtitle text-on-surface-variant md:text-[18px] md:leading-relaxed">
              Harness elite AI agents to optimize your global portfolio in real-time. Experience
              sophisticated, predictive wealth management designed for the modern investor.
            </p>

            <div className="mt-4 flex w-full flex-col gap-4 sm:w-auto sm:flex-row">
              <Link
                to="/dashboard"
                className="flex w-full items-center justify-center gap-2 rounded bg-primary-container px-8 py-4 font-subtitle font-medium text-on-primary transition-all hover:bg-primary sm:w-auto"
              >
                Get Started
                <Icon name="arrow_forward" className="text-lg" />
              </Link>
              <Link
                to="/intelligence"
                className="flex w-full items-center justify-center gap-2 rounded border border-outline-variant bg-surface-container-lowest px-8 py-4 font-subtitle font-medium text-on-surface transition-colors hover:bg-surface-container-low sm:w-auto"
              >
                View Performance
              </Link>
            </div>
          </div>
        </section>

        <section
          id="platform"
          className="mx-auto max-w-container-max px-gutter py-24 md:px-margin"
        >
          <div className="grid grid-cols-1 gap-6 md:auto-rows-[300px] md:grid-cols-3">
            <article className="group relative flex flex-col justify-between overflow-hidden rounded border border-outline-variant bg-surface-container-lowest p-8 md:col-span-2">
              <div>
                <Kicker className="mb-6">Predictive Analysis</Kicker>
                <h3 className="mb-2 font-panel-header text-[24px] text-on-surface">
                  AI-Powered Insights
                </h3>
                <p className="max-w-md font-body text-body text-on-surface-variant">
                  Our predictive models analyze millions of global data points instantly,
                  uncovering institutional-grade opportunities before they hit the broader market.
                </p>
              </div>

              <div className="relative mt-6 flex h-24 items-end border-b border-l border-outline-variant">
                <svg
                  className="h-full w-full text-primary-container"
                  preserveAspectRatio="none"
                  viewBox="0 0 100 40"
                  role="img"
                  aria-label="Model performance trend, rising"
                >
                  <path
                    d="M0,40 L10,30 L25,35 L40,15 L55,20 L75,5 L90,10 L100,0"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                  <path
                    d="M0,40 L10,30 L25,35 L40,15 L55,20 L75,5 L90,10 L100,0 L100,40 L0,40 Z"
                    fill="currentColor"
                    fillOpacity="0.1"
                  />
                </svg>
                <div className="absolute left-[75%] top-[12.5%] h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-container shadow-[0_0_8px_#197a56]" />
              </div>
            </article>

            <article className="relative flex flex-col overflow-hidden rounded border border-outline-variant bg-surface-container-lowest p-8">
              <div className="flex-grow">
                <Kicker className="mb-6">Protection</Kicker>
                <h3 className="mb-2 font-panel-header text-panel-header text-on-surface">
                  Institutional-Grade Security
                </h3>
                <p className="font-body text-body text-on-surface-variant">
                  Military-grade encryption and decentralized custody protocols ensure your assets
                  remain impenetrable.
                </p>
              </div>
              <div className="mt-4 border-t border-outline-variant pt-4">
                <div className="flex items-center justify-between font-footnote text-[11px] uppercase tracking-wider text-on-surface-variant">
                  <span>Status</span>
                  <span className="flex items-center gap-1 font-bold text-primary-container">
                    <Icon name="check_circle" className="text-[14px]" filled />
                    Secure
                  </span>
                </div>
              </div>
            </article>

            <article className="relative flex flex-col overflow-hidden rounded border border-outline-variant bg-surface-container-lowest p-8">
              <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full border border-outline-variant/60 opacity-40" />
              <div className="pointer-events-none absolute -right-6 top-10 h-40 w-40 rounded-full border border-outline-variant/60 opacity-30" />
              <div className="relative z-10 flex-grow">
                <Kicker className="mb-6">Reach</Kicker>
                <h3 className="mb-2 font-panel-header text-panel-header text-on-surface">
                  Global Asset Coverage
                </h3>
                <p className="font-body text-body text-on-surface-variant">
                  Seamlessly manage equities, digital assets, and alternatives across 40+
                  international markets from a single command center.
                </p>
              </div>
            </article>

            <article className="relative flex items-center justify-between overflow-hidden rounded border border-outline-variant bg-surface-container-lowest p-8 md:col-span-2">
              <div>
                <Kicker className="mb-6">Automation</Kicker>
                <h3 className="mb-2 font-panel-header text-[24px] text-on-surface">
                  Real-time Optimization
                </h3>
                <p className="max-w-sm font-body text-body text-on-surface-variant">
                  Automated tax-loss harvesting and dynamic rebalancing keep your portfolio aligned
                  with your risk profile.
                </p>
              </div>
              <RebalancingPanel />
            </article>
          </div>
        </section>
      </main>

      <footer className="mx-auto mt-12 w-full max-w-container-max border-t border-outline-variant/50 bg-surface-container-lowest px-gutter py-12 text-left md:px-margin">
        <p className="font-footnote text-[11px] uppercase tracking-wider text-on-surface-variant">
          © 2026 Lumina Wealth. Intelligence-Driven.
        </p>
      </footer>
    </div>
  )
}
