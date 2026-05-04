import Link from "next/link";

type Crumb = { label: string; href?: string };

export async function SiteHeader({
  crumbs = [],
  liveCount,
}: {
  crumbs?: Crumb[];
  liveCount?: { label: string; value: number | string }[];
}) {
  const tickers = liveCount ?? [];

  return (
    <header className="hairline-b">
      {/* telemetry strip */}
      <div className="hairline-soft-b bg-bg-deep">
        <div className="mx-auto max-w-[1400px] px-6 h-7 flex items-center justify-between text-[11px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
          <div className="flex items-center gap-3">
            <span className="pip pip-live" />
            <span className="text-fg">PIT WALL</span>
            <span aria-hidden>·</span>
            <span>SESSION 001</span>
            <span aria-hidden className="hidden sm:inline">·</span>
            <span className="hidden sm:inline">UTC <Clock /></span>
          </div>
          <div className="hidden md:flex items-center gap-3">
            {tickers.map((s, i) => (
              <span key={i}>
                <span className="text-fg-dim">{s.label} </span>
                <span className="text-fg tabular">{s.value}</span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* main row */}
      <div className="mx-auto max-w-[1400px] px-6 h-16 flex items-center justify-between gap-6">
        <Link href="/" className="flex items-center gap-3 group">
          <Logomark />
          <span className="display-md tracking-tight">
            Carbuildr
            <span className="text-signal">.</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-[12px] tracking-[0.08em] uppercase font-[family-name:var(--font-mono)] text-fg-muted">
          <NavLink href="/parts">Catalog</NavLink>
          <NavLink href="/parts">Categories</NavLink>
          <span className="text-fg-dim">/ Builds <span className="text-signal-2">soon</span></span>
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/parts" className="btn-ghost">Browse</Link>
        </div>
      </div>

      {/* breadcrumb / index strip */}
      {crumbs.length > 0 && (
        <div className="hairline-t bg-bg-deep">
          <div className="mx-auto max-w-[1400px] px-6 h-9 flex items-center gap-3 text-[11px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
            <span className="index-marker">NAV</span>
            <Link href="/" className="hover:text-fg">root</Link>
            {crumbs.map((c, i) => (
              <span key={i} className="flex items-center gap-3">
                <span className="text-line">/</span>
                {c.href ? (
                  <Link href={c.href} className="hover:text-fg">{c.label}</Link>
                ) : (
                  <span className="text-fg">{c.label}</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </header>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="hover:text-fg transition-colors">
      {children}
    </Link>
  );
}

/** Small server-rendered "clock" — formatted at request time. The page is
 *  force-dynamic so this updates each load (close enough to "live" for the strip). */
function Clock() {
  const now = new Date();
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const mm = String(now.getUTCMinutes()).padStart(2, "0");
  return <span className="tabular">{hh}:{mm}</span>;
}

/** Geometric logomark — a stylized lap timing tower / pit board. */
function Logomark() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <rect x="3" y="3" width="18" height="18" stroke="var(--line)" />
      <rect x="3" y="3" width="6" height="6" fill="var(--signal)" />
      <line x1="3" y1="9" x2="21" y2="9" stroke="var(--line)" />
      <line x1="3" y1="15" x2="21" y2="15" stroke="var(--line)" />
      <line x1="9" y1="3" x2="9" y2="21" stroke="var(--line)" />
      <line x1="15" y1="3" x2="15" y2="21" stroke="var(--line)" />
    </svg>
  );
}
