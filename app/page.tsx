import Link from "next/link";
import {
  getCatalogStats,
  listCategoriesWithCounts,
  listPlatforms,
  listAllParts,
  type PlatformSummary,
} from "@/lib/queries/parts";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";
import { VehiclePicker } from "@/app/components/vehicle-picker";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [stats, categories, platforms, parts] = await Promise.all([
    getCatalogStats(),
    listCategoriesWithCounts(),
    listPlatforms(),
    listAllParts(),
  ]);

  // collapse multi-generation chassis into platform groups for display
  const groups = collapseGroups(platforms);

  return (
    <>
      <SiteHeader
        liveCount={[
          { label: "VEH", value: stats.vehicleCount },
          { label: "PARTS", value: stats.partCount },
          { label: "VENDORS", value: stats.vendorCount },
        ]}
      />

      <main className="flex-1">
        {/* ============================================================
            HERO
            ============================================================ */}
        <section className="hero-sweep">
          <div className="mx-auto max-w-[1400px] px-6 pt-24 pb-32 grid grid-cols-12 gap-8">
            {/* left vertical metadata */}
            <aside className="hidden lg:block col-span-2 hairline-r pr-6 pt-2 sticky top-6 self-start">
              <ul className="space-y-6 text-[11px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                <li data-reveal="0">
                  <span className="block text-fg-dim">REGISTRY</span>
                  <span className="block text-fg mt-1">CarPartPicker / 0.1</span>
                </li>
                <li data-reveal="1">
                  <span className="block text-fg-dim">DOMAIN</span>
                  <span className="block text-fg mt-1">Tuner / Bolt-on</span>
                </li>
                <li data-reveal="2">
                  <span className="block text-fg-dim">SCOPE</span>
                  <span className="block text-fg mt-1">8 platforms</span>
                </li>
                <li data-reveal="3">
                  <span className="block text-fg-dim">PHASE</span>
                  <span className="block text-fg mt-1 inline-flex items-center gap-2">
                    <span className="pip" /> 0 — foundation
                  </span>
                </li>
              </ul>
            </aside>

            {/* main hero column */}
            <div className="col-span-12 lg:col-span-8">
              <p className="eyebrow-signal mb-6" data-reveal="0">
                [001] · The PCPartPicker for tuner cars
              </p>
              <h1 className="display-xl" data-reveal="1">
                Build your car.
                <br />
                <span className="text-fg-muted">Skip the </span>
                <span className="relative inline-block">
                  forum tabs
                  <Underline />
                </span>
                <span className="text-signal">.</span>
              </h1>
              <p className="body mt-8 max-w-2xl text-base" data-reveal="2">
                Pick your make, model, year. Get a compatibility-checked catalog of
                bolt-ons, suspension, wheels, and body mods. Assemble a build. Hit{" "}
                <em className="text-fg not-italic">Buy</em> on the cheapest vendor —
                we keep the kickback so the catalog stays free.
              </p>

              <div className="mt-10" data-reveal="3">
                <div id="picker" />
                <VehiclePicker />
                <div className="mt-4">
                  <Link href="#platforms" className="arrow-link">
                    Supported platforms
                  </Link>
                </div>
              </div>

              {/* mini ticker */}
              <div className="mt-16 hairline-t pt-4 grid grid-cols-3 gap-6 max-w-2xl" data-reveal="4">
                <Tick label="LATEST PART" value={parts[0]?.brand ?? "—"} sub={parts[0]?.model ?? "no parts yet"} />
                <Tick label="WORKING VENDOR" value="FCP Euro" sub="JSON-LD parsed" />
                <Tick label="SCRAPER" value="every Mon · 07:00 UTC" sub="GitHub Actions" />
              </div>
            </div>

            {/* right vertical: build sketch */}
            <aside className="hidden lg:block col-span-2 pt-2">
              <BuildPreviewCard />
            </aside>
          </div>
        </section>

        {/* ============================================================
            STATS BAND
            ============================================================ */}
        <section className="hairline-t hairline-b bg-bg-deep">
          <div className="mx-auto max-w-[1400px] px-6 grid grid-cols-2 md:grid-cols-4 divide-x divide-line">
            <Stat label="Vehicles indexed" value={stats.vehicleCount} suffix="rows" />
            <Stat label="Platform groups" value={stats.platformGroups} suffix="chassis" />
            <Stat label="Parts catalog" value={stats.partCount} suffix="parts" />
            <Stat label="Categories" value={stats.categoryCount} suffix="types" />
          </div>
        </section>

        {/* ============================================================
            PLATFORMS
            ============================================================ */}
        <section id="platforms" className="mx-auto max-w-[1400px] px-6 py-24">
          <div className="flex items-end justify-between mb-10 gap-6">
            <div>
              <p className="eyebrow mb-3">[002] · Coverage</p>
              <h2 className="display-lg">Eight platforms.<br/>Deep, not wide.</h2>
            </div>
            <p className="body-sm max-w-md hidden md:block">
              Niche-deep beats wide-shallow at MVP. We cover popular tuner platforms with
              the full Tier 3 mod catalog before expanding the make list.
            </p>
          </div>

          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-line hairline">
            {groups.map((g, i) => (
              <li key={`${g.make}-${g.model}`} className="bg-bg p-5 hover:bg-surface transition-colors group">
                <div className="flex items-start justify-between mb-6">
                  <span className="index-marker">{String(i + 1).padStart(3, "0")}</span>
                  <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.12em] uppercase text-fg-dim">
                    {g.generations.join(" · ")}
                  </span>
                </div>
                <p className="text-[11px] tracking-[0.14em] uppercase text-fg-dim font-[family-name:var(--font-mono)]">
                  {g.make}
                </p>
                <p className="display-md mt-1 text-fg group-hover:text-signal transition-colors">
                  {g.model}
                </p>
                <p className="mt-4 text-[11px] tracking-[0.06em] font-[family-name:var(--font-mono)] text-fg-muted tabular">
                  {g.yearStart}–{g.yearEnd} · {g.rowCount} configs
                </p>
              </li>
            ))}
          </ul>
        </section>

        {/* ============================================================
            CATEGORIES
            ============================================================ */}
        <section className="hairline-t bg-bg-deep">
          <div className="mx-auto max-w-[1400px] px-6 py-24">
            <div className="flex items-end justify-between mb-10 gap-6">
              <div>
                <p className="eyebrow mb-3">[003] · Tier 3 mods</p>
                <h2 className="display-lg">Bolt-on. Suspension.<br/>Wheels. Body.</h2>
              </div>
              <p className="body-sm max-w-md hidden md:block">
                Eighteen mod categories spanning performance, suspension, wheel geometry,
                and aero. Compatibility rules per part. Live vendor pricing.
              </p>
            </div>

            <ul className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-px bg-line hairline">
              {categories.map((c, i) => (
                <li key={c.slug} className="bg-bg-deep">
                  <Link
                    href={`/parts/${c.slug}`}
                    className="block p-4 row-hover h-full"
                  >
                    <div className="flex items-center justify-between">
                      <span className="index-marker">{String(i + 1).padStart(2, "0")}</span>
                      <span className="figure text-[11px] text-fg-dim">{c.partCount}</span>
                    </div>
                    <p className="mt-4 display-md text-fg text-base leading-tight">
                      {c.name}
                    </p>
                    <p className="mt-2 text-[10px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                      /{c.slug}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ============================================================
            PIPELINE
            ============================================================ */}
        <section className="mx-auto max-w-[1400px] px-6 py-24 grid grid-cols-12 gap-8">
          <div className="col-span-12 md:col-span-4">
            <p className="eyebrow mb-3">[004] · How it ships</p>
            <h2 className="display-lg">Spec → Plan → Build.</h2>
            <p className="body-sm mt-6 max-w-sm">
              Phase 0 is the data spine: schema, scraper, read-only catalog. Phase 1
              is the build editor and compatibility engine. Phase 2 expands vendors
              and ships affiliate revenue.
            </p>
          </div>
          <div className="col-span-12 md:col-span-8">
            <ol className="space-y-px bg-line hairline">
              <PipelineRow
                index="01"
                label="SCHEMA"
                title="Postgres on Neon, Drizzle ORM"
                state="shipped"
                detail="9 tables · 4 migrations · bigint cents · numeric wheel/bore"
              />
              <PipelineRow
                index="02"
                label="SEED"
                title="195 vehicles · 18 categories · 6 vendors"
                state="shipped"
                detail="hand-curated platform specs · OEM bore + bolt patterns"
              />
              <PipelineRow
                index="03"
                label="SCRAPER"
                title="FCP Euro · JSON-LD primary path"
                state="shipped"
                detail="rate-limited httpx · idempotent upsert · weekly cron"
              />
              <PipelineRow
                index="04"
                label="UI"
                title="Catalog index + part detail · this site"
                state="shipped"
                detail="Next.js 16 · TypeScript · server components"
              />
              <PipelineRow
                index="05"
                label="BUILD EDITOR"
                title="PCPartPicker-style category rows"
                state="next"
                detail="vehicle picker · compatibility engine · share URL"
              />
              <PipelineRow
                index="06"
                label="EXPAND"
                title="More vendors. Better fitment."
                state="planned"
                detail="ECS Tuning · AmericanMuscle · Haiku LLM fitment fallback"
              />
            </ol>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

/* ============================================================ */

type Group = {
  make: string;
  model: string;
  generations: string[];
  yearStart: number;
  yearEnd: number;
  rowCount: number;
};

function collapseGroups(rows: PlatformSummary[]): Group[] {
  const map = new Map<string, Group>();
  for (const r of rows) {
    const key = `${r.make}/${r.model}`;
    const cur = map.get(key);
    if (!cur) {
      map.set(key, {
        make: r.make,
        model: r.model,
        generations: [r.generation],
        yearStart: r.yearStart,
        yearEnd: r.yearEnd,
        rowCount: r.rowCount,
      });
    } else {
      cur.generations.push(r.generation);
      cur.yearStart = Math.min(cur.yearStart, r.yearStart);
      cur.yearEnd = Math.max(cur.yearEnd, r.yearEnd);
      cur.rowCount += r.rowCount;
    }
  }
  return [...map.values()];
}

function Stat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number;
  suffix: string;
}) {
  return (
    <div className="px-6 py-8 first:pl-0 sm:first:pl-6">
      <p className="eyebrow mb-3">{label}</p>
      <p className="figure text-5xl text-fg flex items-baseline gap-2">
        <span>{value}</span>
        <span className="text-[10px] tracking-[0.16em] uppercase text-fg-dim">{suffix}</span>
      </p>
    </div>
  );
}

function Tick({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <p className="eyebrow text-[10px] mb-2">{label}</p>
      <p className="display-md text-base text-fg leading-tight">{value}</p>
      <p className="text-[11px] font-[family-name:var(--font-mono)] text-fg-dim mt-1">{sub}</p>
    </div>
  );
}

function Underline() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 240 18"
      preserveAspectRatio="none"
      className="absolute -bottom-2 left-0 w-full h-3 text-signal"
    >
      <path
        d="M 2 13 Q 60 2, 120 9 T 238 11"
        stroke="currentColor"
        strokeWidth="2.5"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BuildPreviewCard() {
  return (
    <div className="bracket-frame hairline p-4 bg-surface">
      <p className="eyebrow-signal text-[9px] mb-3">SAMPLE BUILD</p>
      <p className="display-md text-base text-fg">2018 WRX Premium</p>
      <p className="text-[10px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-fg-dim mb-4">
        VA chassis · Stage 1
      </p>
      <ul className="space-y-2 font-[family-name:var(--font-mono)] text-[11px]">
        {[
          ["INTAKE", "Cobb SF"],
          ["EXHAUST", "Invidia N1"],
          ["TUNE", "Cobb AP V3"],
          ["SUSP", "BC BR"],
        ].map(([cat, name]) => (
          <li key={cat} className="flex items-baseline justify-between gap-2 hairline-soft-b pb-1">
            <span className="text-fg-dim">{cat}</span>
            <span className="text-fg text-right">{name}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 hairline-t pt-3 flex items-baseline justify-between font-[family-name:var(--font-mono)] text-[11px]">
        <span className="text-fg-dim uppercase tracking-[0.12em]">Total</span>
        <span className="text-signal tabular">$3,049</span>
      </div>
      <p className="eyebrow-signal text-[9px] mt-4">PHASE 1 PREVIEW</p>
    </div>
  );
}

function PipelineRow({
  index,
  label,
  title,
  state,
  detail,
}: {
  index: string;
  label: string;
  title: string;
  state: "shipped" | "next" | "planned";
  detail: string;
}) {
  const stateMeta = {
    shipped: { pip: "pip", text: "SHIPPED", color: "text-good" },
    next: { pip: "pip pip-amber", text: "NEXT", color: "text-signal" },
    planned: { pip: "pip pip-dim", text: "PLANNED", color: "text-fg-dim" },
  }[state];
  return (
    <li className="bg-bg flex items-center gap-6 px-5 py-4 row-hover">
      <span className="index-marker w-12 shrink-0 tabular">{index}</span>
      <span className="eyebrow w-24 shrink-0">{label}</span>
      <span className="display-md text-base text-fg flex-1 min-w-0 truncate">{title}</span>
      <span className="hidden md:block text-[11px] font-[family-name:var(--font-mono)] text-fg-muted truncate max-w-md">
        {detail}
      </span>
      <span className={`flex items-center gap-2 text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] ${stateMeta.color}`}>
        <span className={stateMeta.pip} />
        {stateMeta.text}
      </span>
    </li>
  );
}
