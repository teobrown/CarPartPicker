import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="hairline-t mt-24">
      <div className="tick-row hairline-b" />
      <div className="mx-auto max-w-[1400px] px-6 py-10 grid gap-8 md:grid-cols-4">
        <div className="md:col-span-2">
          <p className="display-md">
            Carbuildr<span className="text-signal">.</span>
          </p>
          <p className="body-sm mt-3 max-w-md">
            A compatibility-checked catalog of bolt-on, suspension, wheel, and body mods
            for 8 tuner platforms. Affiliate buy-through. No forum tabs required.
          </p>
        </div>
        <div>
          <p className="eyebrow mb-3">Catalog</p>
          <ul className="space-y-2 body-sm">
            <li><Link href="/parts" className="hover:text-fg">All parts</Link></li>
            <li><Link href="/parts/cold-air-intake" className="hover:text-fg">Cold Air Intake</Link></li>
            <li><Link href="/parts/catback-exhaust" className="hover:text-fg">Catback</Link></li>
            <li><Link href="/parts/coilovers" className="hover:text-fg">Coilovers</Link></li>
            <li><Link href="/parts/wheels" className="hover:text-fg">Wheels</Link></li>
          </ul>
        </div>
        <div>
          <p className="eyebrow mb-3">About</p>
          <ul className="space-y-2 body-sm font-[family-name:var(--font-mono)] text-[12px]">
            <li><span className="pip pip-live mr-2 -translate-y-[1px] inline-block" />Live · catalog growing</li>
            <li><span className="pip mr-2 -translate-y-[1px] inline-block" />Compatibility-checked</li>
            <li><span className="pip mr-2 -translate-y-[1px] inline-block" />Affiliate-supported · free for users</li>
          </ul>
        </div>
      </div>
      <div className="hairline-t">
        <div className="mx-auto max-w-[1400px] px-6 py-4 flex items-center justify-between text-[11px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
          <span>© 2026 Carbuildr</span>
          <span>Built for people who build cars</span>
        </div>
      </div>
    </footer>
  );
}
