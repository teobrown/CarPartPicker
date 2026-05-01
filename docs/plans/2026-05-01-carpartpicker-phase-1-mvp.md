# CarPartPicker — Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make the site DO the thing it promises. Vehicle-aware compatibility-checked builds at a shareable anonymous URL, with affiliate buy-through.

**Architecture:** Same monorepo. New routes (`/build/[slug]`, `/go/[listingId]`, `/api/builds/*`), a vehicle-context system (cookie-backed, server-readable), a compatibility query helper, a part picker modal as a client component, and an affiliate redirector that logs clicks. No new services.

**Tech Stack additions:** `nanoid` for slug generation. No new infra otherwise. `next/headers` for cookie reads in server components.

**Reference:** `docs/specs/2026-04-30-carpartpicker-design.md` §5–§7.

---

## Repository additions

```
app/
├── build/[slug]/page.tsx               # build editor
├── build/[slug]/edit-actions.ts        # server actions: add/remove/update build items
├── go/[listingId]/route.ts             # affiliate redirector
├── api/builds/route.ts                 # POST: create build (vehicle picker submit target)
├── components/
│   ├── vehicle-picker.tsx              # client component: cascading dropdowns
│   ├── vehicle-context.tsx             # cookie-backed SelectedVehicle indicator
│   ├── compat-badge.tsx                # status pill for parts
│   ├── part-picker-modal.tsx           # client component: open from a build row
│   └── build-summary.tsx               # warnings banner + total
├── api/vehicles/route.ts               # vehicle picker dropdowns data
├── api/parts/search/route.ts           # part picker modal data (compat-ranked)
├── not-found.tsx                       # global 404
├── error.tsx                           # error boundary
├── sitemap.ts                          # next sitemap
└── robots.ts                           # next robots.txt
lib/
├── queries/
│   ├── builds.ts                       # build CRUD + items
│   └── compat.ts                       # compatibility ranking
└── slug.ts                             # nanoid slug helpers
```

---

## Task 1: Build creation + slug routing + cookie-backed vehicle context

**What you're building:** A user can pick a vehicle (make/model/year/trim cascading dropdowns) on the landing page, click "Start build," and land on `/build/[slug]` (a brand-new build with their vehicle attached). The selected vehicle persists in a cookie so subsequent pages know context.

**Files:**
- Create: `lib/slug.ts`
- Create: `lib/queries/builds.ts`
- Create: `app/api/vehicles/route.ts`
- Create: `app/api/builds/route.ts`
- Create: `app/components/vehicle-picker.tsx`
- Create: `app/components/vehicle-context.tsx`
- Create: `app/build/[slug]/page.tsx` (skeleton — full editor in Task 2)
- Modify: `app/page.tsx` — replace the existing CTA buttons with the vehicle picker
- Modify: `app/components/site-header.tsx` — show selected vehicle in the telemetry strip when set
- Test: `tests/unit/builds.queries.test.ts`

### Step 1.1: Install nanoid

```bash
npm install nanoid
```

### Step 1.2: Failing test for build queries

```ts
// tests/unit/builds.queries.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { builds, buildItems, vehicles } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import { createBuild, getBuild, addBuildItem, removeBuildItem } from '@/lib/queries/builds';

let vehicleId: number;

beforeAll(async () => {
  await db.execute(sql`TRUNCATE TABLE build_items, builds RESTART IDENTITY CASCADE`);
  // ensure at least one vehicle exists; the seed test runs file-level beforeAll
  const v = (await db.select().from(vehicles).limit(1))[0];
  if (!v) throw new Error('vehicles must be seeded; run seed.test.ts first');
  vehicleId = v.id;
});

describe('build queries', () => {
  it('createBuild returns a build with an 8-char slug and the right vehicle', async () => {
    const b = await createBuild({ vehicleId });
    expect(b.slug).toMatch(/^[A-Za-z0-9_-]{8}$/);
    expect(b.vehicleId).toBe(vehicleId);
  });

  it('getBuild returns the build with its vehicle and zero items by default', async () => {
    const b = await createBuild({ vehicleId });
    const found = await getBuild(b.slug);
    expect(found).toBeTruthy();
    expect(found!.vehicle.id).toBe(vehicleId);
    expect(found!.items.length).toBe(0);
  });

  it('addBuildItem appends a part at the next position; removeBuildItem deletes it', async () => {
    const b = await createBuild({ vehicleId });
    // we need ANY part — insert a stub directly to keep this test self-contained
    const { parts, categories } = await import('@/lib/db/schema');
    const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p] = await db
      .insert(parts)
      .values({
        categoryId: c.id, brand: 'Test', model: 'Stub Intake',
        name: 'Test Stub Intake',
      })
      .returning();
    await addBuildItem({ buildSlug: b.slug, partId: p.id });
    let after = await getBuild(b.slug);
    expect(after!.items.length).toBe(1);
    expect(after!.items[0].part.id).toBe(p.id);
    await removeBuildItem({ buildSlug: b.slug, partId: p.id });
    after = await getBuild(b.slug);
    expect(after!.items.length).toBe(0);
  });
});
```

### Step 1.3: Implement slug helper

```ts
// lib/slug.ts
import { customAlphabet } from 'nanoid';

// 8 chars × 64 alphabet ≈ 2.8 × 10^14 possibilities; collision-safe for ≤10M builds.
const ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-';
const generate = customAlphabet(ALPHABET, 8);

export function newBuildSlug(): string {
  return generate();
}
```

### Step 1.4: Implement build queries

```ts
// lib/queries/builds.ts
import { db } from '@/lib/db/client';
import { builds, buildItems, parts, categories, vehicles, vendorListings, vendors } from '@/lib/db/schema';
import { eq, sql, max } from 'drizzle-orm';
import { newBuildSlug } from '@/lib/slug';

export type BuildItemRow = {
  position: number;
  userNote: string | null;
  part: {
    id: number;
    brand: string;
    model: string;
    name: string;
    categorySlug: string;
    cheapestPriceCents: number | null;
    vendorCount: number;
  };
};

export type BuildDetail = {
  id: number;
  slug: string;
  createdAt: Date;
  vehicle: {
    id: number;
    make: string;
    model: string;
    year: number;
    trim: string | null;
    subModel: string | null;
    generation: string;
  };
  items: BuildItemRow[];
};

export async function createBuild(opts: { vehicleId: number }): Promise<{ id: number; slug: string; vehicleId: number }> {
  // retry on collision (shouldn't happen but cheap insurance)
  for (let attempt = 0; attempt < 5; attempt++) {
    const slug = newBuildSlug();
    try {
      const [row] = await db
        .insert(builds)
        .values({ slug, vehicleId: opts.vehicleId })
        .returning({ id: builds.id, slug: builds.slug, vehicleId: builds.vehicleId });
      return row;
    } catch (e) {
      // unique violation; loop and try a new slug
      if (attempt === 4) throw e;
    }
  }
  throw new Error('unreachable');
}

export async function getBuild(slug: string): Promise<BuildDetail | null> {
  const [b] = await db
    .select({
      id: builds.id,
      slug: builds.slug,
      createdAt: builds.createdAt,
      vehicleId: vehicles.id,
      make: vehicles.make,
      model: vehicles.model,
      year: vehicles.year,
      trim: vehicles.trim,
      subModel: vehicles.subModel,
      generation: vehicles.generation,
    })
    .from(builds)
    .innerJoin(vehicles, eq(vehicles.id, builds.vehicleId))
    .where(eq(builds.slug, slug))
    .limit(1);
  if (!b) return null;

  const itemRows = await db
    .select({
      position: buildItems.position,
      userNote: buildItems.userNote,
      partId: parts.id,
      brand: parts.brand,
      partModel: parts.model,
      name: parts.name,
      categorySlug: categories.slug,
    })
    .from(buildItems)
    .innerJoin(parts, eq(parts.id, buildItems.partId))
    .innerJoin(categories, eq(categories.id, parts.categoryId))
    .where(eq(buildItems.buildId, b.id))
    .orderBy(buildItems.position);

  // attach pricing per part
  const items: BuildItemRow[] = await Promise.all(
    itemRows.map(async (r) => {
      const listings = await db
        .select({ priceCents: vendorListings.priceCents, vendorId: vendorListings.vendorId })
        .from(vendorListings)
        .where(eq(vendorListings.partId, r.partId));
      const cheapest = listings.reduce<number | null>((acc, l) => {
        if (l.priceCents == null) return acc;
        return acc == null || l.priceCents < acc ? l.priceCents : acc;
      }, null);
      const vendorCount = new Set(listings.map((l) => l.vendorId)).size;
      return {
        position: r.position,
        userNote: r.userNote,
        part: {
          id: r.partId,
          brand: r.brand,
          model: r.partModel,
          name: r.name,
          categorySlug: r.categorySlug,
          cheapestPriceCents: cheapest,
          vendorCount,
        },
      };
    }),
  );

  return {
    id: b.id,
    slug: b.slug,
    createdAt: b.createdAt,
    vehicle: {
      id: b.vehicleId,
      make: b.make,
      model: b.model,
      year: b.year,
      trim: b.trim,
      subModel: b.subModel,
      generation: b.generation,
    },
    items,
  };
}

export async function addBuildItem(opts: { buildSlug: string; partId: number; note?: string | null }): Promise<void> {
  const [b] = await db.select({ id: builds.id }).from(builds).where(eq(builds.slug, opts.buildSlug)).limit(1);
  if (!b) throw new Error(`build not found: ${opts.buildSlug}`);
  const [{ next }] = await db
    .select({ next: sql<number>`COALESCE(${max(buildItems.position)}, 0) + 1` })
    .from(buildItems)
    .where(eq(buildItems.buildId, b.id));
  await db.insert(buildItems).values({
    buildId: b.id,
    partId: opts.partId,
    position: next,
    userNote: opts.note ?? null,
  });
  await db.update(builds).set({ updatedAt: new Date() }).where(eq(builds.id, b.id));
}

export async function removeBuildItem(opts: { buildSlug: string; partId: number }): Promise<void> {
  const [b] = await db.select({ id: builds.id }).from(builds).where(eq(builds.slug, opts.buildSlug)).limit(1);
  if (!b) throw new Error(`build not found: ${opts.buildSlug}`);
  await db.delete(buildItems).where(sql`${buildItems.buildId} = ${b.id} AND ${buildItems.partId} = ${opts.partId}`);
  await db.update(builds).set({ updatedAt: new Date() }).where(eq(builds.id, b.id));
}
```

### Step 1.5: Vehicles dropdown API

```ts
// app/api/vehicles/route.ts
import { NextRequest } from 'next/server';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { sql, eq, and } from 'drizzle-orm';

// returns the next-level options for cascading make → model → year → trim
export async function GET(req: NextRequest) {
  const make = req.nextUrl.searchParams.get('make');
  const model = req.nextUrl.searchParams.get('model');
  const year = req.nextUrl.searchParams.get('year');

  if (!make) {
    const rows = await db.select({ make: vehicles.make }).from(vehicles).groupBy(vehicles.make).orderBy(vehicles.make);
    return Response.json({ level: 'make', options: rows.map((r) => r.make) });
  }
  if (!model) {
    const rows = await db
      .select({ model: vehicles.model })
      .from(vehicles)
      .where(eq(vehicles.make, make))
      .groupBy(vehicles.model)
      .orderBy(vehicles.model);
    return Response.json({ level: 'model', options: rows.map((r) => r.model) });
  }
  if (!year) {
    const rows = await db
      .select({ year: vehicles.year })
      .from(vehicles)
      .where(and(eq(vehicles.make, make), eq(vehicles.model, model)))
      .groupBy(vehicles.year)
      .orderBy(sql`${vehicles.year} DESC`);
    return Response.json({ level: 'year', options: rows.map((r) => r.year) });
  }
  // trim list (with vehicle ID for each)
  const rows = await db
    .select({
      id: vehicles.id,
      trim: vehicles.trim,
      subModel: vehicles.subModel,
      generation: vehicles.generation,
    })
    .from(vehicles)
    .where(and(eq(vehicles.make, make), eq(vehicles.model, model), eq(vehicles.year, Number(year))))
    .orderBy(vehicles.subModel, vehicles.trim);
  return Response.json({ level: 'trim', options: rows });
}
```

### Step 1.6: Build creation API

```ts
// app/api/builds/route.ts
import { NextRequest } from 'next/server';
import { cookies } from 'next/headers';
import { createBuild } from '@/lib/queries/builds';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const vehicleId = Number(body?.vehicleId);
  if (!vehicleId || Number.isNaN(vehicleId)) {
    return Response.json({ error: 'vehicleId required' }, { status: 400 });
  }
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, vehicleId)).limit(1);
  if (!v) return Response.json({ error: 'vehicle not found' }, { status: 404 });
  const b = await createBuild({ vehicleId });
  // remember the vehicle for future page loads
  const c = await cookies();
  c.set('cpp_vehicle_id', String(vehicleId), { path: '/', maxAge: 60 * 60 * 24 * 90 });
  return Response.json({ slug: b.slug });
}
```

### Step 1.7: Vehicle picker (client component)

```tsx
// app/components/vehicle-picker.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

type Step = 'make' | 'model' | 'year' | 'trim';

export function VehiclePicker() {
  const router = useRouter();
  const [make, setMake] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);

  const [makes, setMakes] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [trims, setTrims] = useState<{ id: number; trim: string | null; subModel: string | null; generation: string }[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // load makes on mount
  useEffect(() => {
    void fetchOptions('make').then((d) => setMakes(d.options as string[]));
  }, []);
  useEffect(() => {
    if (!make) { setModels([]); setModelName(null); return; }
    void fetchOptions('model', { make }).then((d) => setModels(d.options as string[]));
  }, [make]);
  useEffect(() => {
    if (!make || !modelName) { setYears([]); setYear(null); return; }
    void fetchOptions('year', { make, model: modelName }).then((d) => setYears(d.options as number[]));
  }, [make, modelName]);
  useEffect(() => {
    if (!make || !modelName || !year) { setTrims([]); setVehicleId(null); return; }
    void fetchOptions('trim', { make, model: modelName, year: String(year) }).then((d) => setTrims(d.options as typeof trims));
  }, [make, modelName, year]);

  async function startBuild() {
    if (!vehicleId) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await fetch('/api/builds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicleId }),
      });
      if (!r.ok) {
        setError('Could not start build. Try again.');
        return;
      }
      const { slug } = await r.json();
      router.push(`/build/${slug}`);
    } catch {
      setError('Network error.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="hairline bg-surface p-5">
      <p className="eyebrow-signal text-[10px] mb-4">[VEH] · Pick your platform</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Select label="Make"   value={make ?? ''}      options={makes.map((m) => ({ label: m, value: m }))}                                              onChange={(v) => { setMake(v || null); setModelName(null); setYear(null); setVehicleId(null); }} />
        <Select label="Model"  value={modelName ?? ''} options={models.map((m) => ({ label: m, value: m }))}                                             onChange={(v) => { setModelName(v || null); setYear(null); setVehicleId(null); }} disabled={!make} />
        <Select label="Year"   value={year ? String(year) : ''} options={years.map((y) => ({ label: String(y), value: String(y) }))}                  onChange={(v) => { setYear(v ? Number(v) : null); setVehicleId(null); }} disabled={!modelName} />
        <Select label="Trim"   value={vehicleId ? String(vehicleId) : ''}
                options={trims.map((t) => ({ label: trimLabel(t), value: String(t.id) }))}
                onChange={(v) => setVehicleId(v ? Number(v) : null)}
                disabled={!year} />
      </div>
      {error && <p className="text-danger eyebrow text-[10px] mt-3">{error}</p>}
      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={startBuild}
          disabled={!vehicleId || submitting}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? 'STARTING…' : 'START BUILD →'}
        </button>
        <a href="/parts" className="arrow-link">Or browse the catalog</a>
      </div>
    </div>
  );
}

function trimLabel(t: { trim: string | null; subModel: string | null; generation: string }) {
  return [t.subModel, t.trim, `(${t.generation})`].filter(Boolean).join(' · ');
}

async function fetchOptions(level: Step, params: Record<string, string> = {}) {
  const u = new URL('/api/vehicles', window.location.origin);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const r = await fetch(u.toString());
  if (!r.ok) throw new Error(`fetch failed: ${r.status}`);
  return (await r.json()) as { level: Step; options: unknown[] };
}

function Select({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: { label: string; value: string }[];
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="eyebrow text-[10px]">{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full bg-bg-deep hairline px-3 py-2 text-sm font-[family-name:var(--font-mono)] text-fg disabled:text-fg-dim disabled:cursor-not-allowed appearance-none"
      >
        <option value="">{disabled ? '—' : `Select ${label.toLowerCase()}`}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
```

### Step 1.8: Vehicle context indicator + cookie reader

```tsx
// app/components/vehicle-context.tsx
import { cookies } from 'next/headers';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import Link from 'next/link';

export type SelectedVehicle = {
  id: number;
  make: string;
  model: string;
  year: number;
  trim: string | null;
  subModel: string | null;
  generation: string;
};

/** Server helper: returns the currently-selected vehicle from cookie, if any. */
export async function getSelectedVehicle(): Promise<SelectedVehicle | null> {
  const c = await cookies();
  const id = Number(c.get('cpp_vehicle_id')?.value);
  if (!id || Number.isNaN(id)) return null;
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, id)).limit(1);
  if (!v) return null;
  return {
    id: v.id,
    make: v.make,
    model: v.model,
    year: v.year,
    trim: v.trim,
    subModel: v.subModel,
    generation: v.generation,
  };
}

export function vehicleLabel(v: SelectedVehicle): string {
  return `${v.year} ${v.make} ${v.model}${v.subModel ? ' ' + v.subModel : ''}${v.trim ? ' · ' + v.trim : ''}`;
}

/** Inline indicator for the header strip. */
export async function VehicleIndicator() {
  const v = await getSelectedVehicle();
  if (!v) return null;
  return (
    <Link
      href="/#picker"
      className="hidden md:flex items-center gap-2 text-fg hover:text-signal"
    >
      <span className="pip pip-amber" />
      <span>{vehicleLabel(v)}</span>
    </Link>
  );
}
```

### Step 1.9: Wire vehicle picker into the landing page

In `app/page.tsx`, replace the current CTA buttons block (the one with "ENTER CATALOG" and "Supported platforms") with:
```tsx
<div className="mt-10" data-reveal="3">
  <div id="picker" />
  {/* @ts-expect-error Async Server Component import — VehiclePicker is a client component, fine */}
  <VehiclePicker />
</div>
```
…and add `import { VehiclePicker } from '@/app/components/vehicle-picker';` to the top.

### Step 1.10: Update site header to show selected vehicle

In `app/components/site-header.tsx`, the header is currently a sync function. Convert it to async so it can `await getSelectedVehicle()`. Replace the "PIT WALL · SESSION 001 · UTC HH:MM" strip's right side: when a vehicle is selected, show the vehicle indicator instead of (or in addition to) the count tickers.

Render it as: `[count tickers] [vertical separator] [vehicle indicator]` — both visible on md+.

### Step 1.11: Build editor skeleton

```tsx
// app/build/[slug]/page.tsx
import { notFound } from 'next/navigation';
import { getBuild } from '@/lib/queries/builds';
import { SiteHeader } from '@/app/components/site-header';
import { SiteFooter } from '@/app/components/site-footer';

export const dynamic = 'force-dynamic';

export default async function BuildPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const build = await getBuild(slug);
  if (!build) return notFound();
  return (
    <>
      <SiteHeader crumbs={[{ label: 'build', href: '/parts' }, { label: slug }]} />
      <main className="mx-auto max-w-[1400px] px-6 py-12 flex-1">
        <p className="eyebrow-signal mb-4">[BUILD] · {slug}</p>
        <h1 className="display-lg">
          {build.vehicle.year} {build.vehicle.make} {build.vehicle.model}
          {build.vehicle.subModel ? ' ' + build.vehicle.subModel : ''}
        </h1>
        <p className="body-sm mt-2">
          {build.vehicle.trim ? build.vehicle.trim + ' · ' : ''}
          {build.vehicle.generation} chassis · {build.items.length} parts in build
        </p>
        <p className="eyebrow mt-12 text-fg-dim">Build editor lands in Task 2.</p>
      </main>
      <SiteFooter />
    </>
  );
}
```

### Step 1.12: Run tests + verify

```bash
npm test                # adds builds.queries.test.ts to the suite (expect +3 tests)
npm run build
```

Both should pass. Then run the dev server and walk through: home → pick vehicle → click START BUILD → land on /build/[slug] → see the placeholder.

### Step 1.13: Commit

```bash
git add -A
git commit -m "feat(builds): vehicle picker, build creation, /build/[slug] route, cookie-backed vehicle context"
```

---

## Task 2: Build editor + part picker modal + add/remove

**What you're building:** The `/build/[slug]` page becomes interactive. PCPartPicker-style category rows; click "+ Add" on any row to open a modal that searches parts in that category (compat-ranked); click a part to add it to the build via a server action; remove buttons on each row; build total updates live; warnings banner placeholder.

**Files:**
- Create: `app/build/[slug]/edit-actions.ts` (Next.js server actions)
- Create: `app/components/part-picker-modal.tsx`
- Create: `app/components/build-row.tsx`
- Create: `app/components/build-summary.tsx`
- Create: `app/api/parts/search/route.ts`
- Modify: `app/build/[slug]/page.tsx` (full editor)

### Step 2.1: Failing test for the search API

```ts
// tests/unit/parts.search.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { parts, categories, vendors, vendorListings, vehicles } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';

let categoryId: number;
let vehicleId: number;

beforeAll(async () => {
  await db.execute(sql`TRUNCATE TABLE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`);
  const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
  categoryId = c.id;
  const [v] = await db.select().from(vehicles).where(eq(vehicles.model, 'WRX')).limit(1);
  vehicleId = v.id;
  // insert 3 parts: one without fitment (unknown), one with fitting rule, one incompatible
  const [vendor] = await db.select().from(vendors).where(eq(vendors.slug, 'fcp-euro')).limit(1);
  const inserted = await db.insert(parts).values([
    { categoryId, brand: 'Cobb',    model: 'SF Intake',  name: 'Cobb SF Intake' },
    { categoryId, brand: 'AEM',     model: 'Air Intake', name: 'AEM Air Intake' },
    { categoryId, brand: 'Generic', model: 'Cone Filter',name: 'Generic Cone Filter' },
  ]).returning();
  for (const p of inserted) {
    await db.insert(vendorListings).values({ partId: p.id, vendorId: vendor.id, vendorUrl: 'https://example.com', priceCents: 30000, inStock: true });
  }
});

describe('GET /api/parts/search', () => {
  it('returns parts in the given category', async () => {
    const url = `http://localhost:3000/api/parts/search?category=intake`;
    const r = await fetch(url);
    expect(r.status).toBe(200);
    const data = await r.json();
    expect(data.parts.length).toBeGreaterThanOrEqual(3);
  });

  it('returns parts ranked by compat status when vehicleId is given', async () => {
    const url = `http://localhost:3000/api/parts/search?category=intake&vehicleId=${vehicleId}`;
    const r = await fetch(url);
    const data = await r.json();
    expect(data.parts[0]).toHaveProperty('status');
  });
});
```

(Note: this test requires the dev server running. Mark it as integration. If running it without a dev server is preferred, instead test the underlying query function directly — see Step 2.4 — and skip the HTTP layer.)

### Step 2.2: Compatibility query helper

```ts
// lib/queries/compat.ts
import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, fitmentRules, vehicles } from '@/lib/db/schema';
import { sql, eq, and, or, isNull, min } from 'drizzle-orm';

export type CompatStatus = 'fits' | 'fits_with_caveat' | 'unknown' | 'incompatible';

export type RankedPartRow = {
  id: number;
  brand: string;
  model: string;
  name: string;
  imageUrl: string | null;
  cheapestPriceCents: number | null;
  vendorCount: number;
  status: CompatStatus;
  caveat: string | null;
};

const STATUS_PRIORITY: Record<CompatStatus, number> = {
  fits: 3,
  fits_with_caveat: 2,
  unknown: 1,
  incompatible: 0,
};

/** Rank parts in a category by compatibility for a given vehicle. If vehicleId is null, everything is "unknown". */
export async function listCategoryPartsRankedForVehicle(opts: {
  categorySlug: string;
  vehicleId: number | null;
  search?: string;
}): Promise<RankedPartRow[]> {
  const { categorySlug, vehicleId, search } = opts;

  // Step 1: fetch all parts in the category with cheapest price + vendor count
  const baseRows = await db
    .select({
      id: parts.id,
      brand: parts.brand,
      model: parts.model,
      name: parts.name,
      imageUrl: parts.imageUrl,
      cheapestPriceCents: min(vendorListings.priceCents),
      vendorCount: sql<number>`count(distinct ${vendorListings.vendorId})::int`,
    })
    .from(parts)
    .innerJoin(categories, eq(categories.id, parts.categoryId))
    .leftJoin(vendorListings, eq(vendorListings.partId, parts.id))
    .where(
      and(
        eq(categories.slug, categorySlug),
        search ? sql`(${parts.brand} ILIKE ${'%' + search + '%'} OR ${parts.model} ILIKE ${'%' + search + '%'} OR ${parts.name} ILIKE ${'%' + search + '%'})` : sql`true`,
      ),
    )
    .groupBy(parts.id);

  if (vehicleId == null) {
    return baseRows.map((r) => ({ ...r, status: 'unknown' as const, caveat: null }));
  }

  // Step 2: get the vehicle row to drive matching
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, vehicleId)).limit(1);
  if (!v) {
    return baseRows.map((r) => ({ ...r, status: 'unknown' as const, caveat: null }));
  }

  // Step 3: for each part, find matching fitment rules and pick the highest-priority status
  const rules = await db
    .select()
    .from(fitmentRules)
    .where(
      sql`${fitmentRules.partId} IN (${sql.raw(baseRows.map((r) => r.id).join(',') || '0')})`,
    );

  function ruleMatches(r: typeof rules[number]): boolean {
    if (r.make != null && r.make !== v.make) return false;
    if (r.model != null && r.model !== v.model) return false;
    if (r.generation != null && r.generation !== v.generation) return false;
    if (r.yearStart != null && v.year < r.yearStart) return false;
    if (r.yearEnd != null && v.year > r.yearEnd) return false;
    if (r.bodyStyle != null && r.bodyStyle !== v.bodyStyle) return false;
    if (r.trimsIncluded && r.trimsIncluded.length > 0 && (!v.trim || !r.trimsIncluded.includes(v.trim))) return false;
    if (r.trimsExcluded && r.trimsExcluded.length > 0 && v.trim && r.trimsExcluded.includes(v.trim)) return false;
    return true;
  }

  const byPart: Record<number, { status: CompatStatus; caveat: string | null }> = {};
  for (const rule of rules) {
    if (!ruleMatches(rule)) continue;
    const status = (rule.status as CompatStatus) ?? 'unknown';
    const cur = byPart[rule.partId];
    if (!cur || STATUS_PRIORITY[status] > STATUS_PRIORITY[cur.status]) {
      byPart[rule.partId] = { status, caveat: rule.caveat };
    }
  }

  return baseRows
    .map((r) => ({
      ...r,
      status: (byPart[r.id]?.status ?? 'unknown') as CompatStatus,
      caveat: byPart[r.id]?.caveat ?? null,
    }))
    .sort((a, b) => STATUS_PRIORITY[b.status] - STATUS_PRIORITY[a.status]);
}
```

### Step 2.3: Search API route

```ts
// app/api/parts/search/route.ts
import { NextRequest } from 'next/server';
import { listCategoryPartsRankedForVehicle } from '@/lib/queries/compat';

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const category = sp.get('category');
  if (!category) return Response.json({ error: 'category required' }, { status: 400 });
  const vehicleId = sp.get('vehicleId') ? Number(sp.get('vehicleId')) : null;
  const search = sp.get('q') ?? undefined;
  const parts = await listCategoryPartsRankedForVehicle({ categorySlug: category, vehicleId, search });
  return Response.json({ parts });
}
```

### Step 2.4: Server actions for build edits

```ts
// app/build/[slug]/edit-actions.ts
'use server';

import { revalidatePath } from 'next/cache';
import { addBuildItem, removeBuildItem } from '@/lib/queries/builds';

export async function addItemAction({ slug, partId }: { slug: string; partId: number }) {
  await addBuildItem({ buildSlug: slug, partId });
  revalidatePath(`/build/${slug}`);
}

export async function removeItemAction({ slug, partId }: { slug: string; partId: number }) {
  await removeBuildItem({ buildSlug: slug, partId });
  revalidatePath(`/build/${slug}`);
}
```

### Step 2.5: Compat badge component

```tsx
// app/components/compat-badge.tsx
import type { CompatStatus } from '@/lib/queries/compat';

export function CompatBadge({ status, caveat }: { status: CompatStatus; caveat?: string | null }) {
  const meta = {
    fits: { pip: 'pip', label: 'Fits', color: 'text-good' },
    fits_with_caveat: { pip: 'pip pip-amber', label: 'Caveat', color: 'text-signal' },
    unknown: { pip: 'pip pip-dim', label: 'Unknown', color: 'text-fg-muted' },
    incompatible: { pip: 'pip pip-red', label: 'No fit', color: 'text-danger' },
  }[status];
  return (
    <span className={`inline-flex items-center gap-2 text-[10px] tracking-[0.12em] uppercase font-[family-name:var(--font-mono)] ${meta.color}`} title={caveat ?? undefined}>
      <span className={meta.pip} />
      {meta.label}
    </span>
  );
}
```

### Step 2.6: Build summary (warnings banner + total)

```tsx
// app/components/build-summary.tsx
import type { BuildDetail } from '@/lib/queries/builds';
import { formatPrice } from '@/lib/format';

export function BuildSummary({ build }: { build: BuildDetail }) {
  const total = build.items.reduce<number>((acc, it) => acc + (it.part.cheapestPriceCents ?? 0), 0);

  return (
    <div className="hairline bg-bg-deep">
      <div className="px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="pip pip-amber" />
          <span className="eyebrow-signal text-[11px]">PHASE 1 PREVIEW · COMPAT ENGINE LIVE</span>
        </div>
        <span className="font-[family-name:var(--font-mono)] text-[12px] text-fg-muted">
          {build.items.length} parts · last updated {new Date(build.createdAt).toISOString().slice(0, 16).replace('T', ' ')}
        </span>
      </div>
      <div className="hairline-t px-5 py-4 flex items-baseline justify-between">
        <span className="eyebrow">Total</span>
        <span className="figure text-3xl text-signal">{formatPrice(total)}</span>
      </div>
    </div>
  );
}
```

### Step 2.7: Part picker modal (client component)

```tsx
// app/components/part-picker-modal.tsx
'use client';

import { useEffect, useState, useTransition } from 'react';
import { addItemAction } from '@/app/build/[slug]/edit-actions';
import { CompatBadge } from './compat-badge';
import { formatPrice } from '@/lib/format';
import type { CompatStatus } from '@/lib/queries/compat';

export type PartPickerProps = {
  open: boolean;
  onClose: () => void;
  buildSlug: string;
  vehicleId: number;
  categorySlug: string;
  categoryLabel: string;
};

type Row = {
  id: number;
  brand: string;
  model: string;
  name: string;
  cheapestPriceCents: number | null;
  vendorCount: number;
  status: CompatStatus;
  caveat: string | null;
};

export function PartPickerModal(p: PartPickerProps) {
  const [rows, setRows] = useState<Row[]>([]);
  const [q, setQ] = useState('');
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!p.open) return;
    const u = new URL('/api/parts/search', window.location.origin);
    u.searchParams.set('category', p.categorySlug);
    u.searchParams.set('vehicleId', String(p.vehicleId));
    if (q) u.searchParams.set('q', q);
    void fetch(u.toString())
      .then((r) => r.json())
      .then((d) => setRows(d.parts as Row[]));
  }, [p.open, p.categorySlug, p.vehicleId, q]);

  if (!p.open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={p.onClose} />
      <div className="relative w-full md:max-w-3xl max-h-[85vh] overflow-hidden bg-bg hairline flex flex-col">
        <div className="hairline-b px-5 py-4 flex items-center justify-between">
          <div>
            <p className="eyebrow-signal text-[10px]">[PICK PART]</p>
            <h3 className="display-md text-base mt-1">{p.categoryLabel}</h3>
          </div>
          <button onClick={p.onClose} className="btn-ghost">CLOSE</button>
        </div>
        <div className="hairline-b px-5 py-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by brand or model…"
            className="w-full bg-bg-deep hairline px-3 py-2 text-sm font-[family-name:var(--font-mono)] text-fg"
          />
        </div>
        <ul className="overflow-y-auto">
          {rows.map((r) => (
            <li key={r.id}>
              <button
                onClick={() =>
                  startTransition(async () => {
                    await addItemAction({ slug: p.buildSlug, partId: r.id });
                    p.onClose();
                  })
                }
                className="row-hover hairline-soft-b py-3 px-5 grid grid-cols-12 gap-3 items-baseline w-full text-left disabled:opacity-50"
                disabled={isPending}
              >
                <span className="col-span-1 index-marker tabular">{String(r.id).padStart(3, '0')}</span>
                <span className="col-span-4 min-w-0">
                  <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">{r.brand}</span>
                  <span className="display-md text-base text-fg leading-tight truncate block">{r.model}</span>
                </span>
                <span className="col-span-3"><CompatBadge status={r.status} caveat={r.caveat} /></span>
                <span className="col-span-2 figure text-fg text-right">{formatPrice(r.cheapestPriceCents)}</span>
                <span className="col-span-2 text-right text-[11px] text-fg-muted">×{r.vendorCount}</span>
              </button>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="px-5 py-12 text-center body-sm">No parts in this category yet.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
```

### Step 2.8: Build row (client component for the modal trigger and remove button)

```tsx
// app/components/build-row.tsx
'use client';

import { useState, useTransition } from 'react';
import Link from 'next/link';
import { PartPickerModal } from './part-picker-modal';
import { CompatBadge } from './compat-badge';
import { removeItemAction } from '@/app/build/[slug]/edit-actions';
import type { BuildItemRow } from '@/lib/queries/builds';
import { partSlug, formatPrice } from '@/lib/format';

type Props = {
  buildSlug: string;
  vehicleId: number;
  categorySlug: string;
  categoryLabel: string;
  item: (BuildItemRow & { compatStatus?: 'fits' | 'fits_with_caveat' | 'unknown' | 'incompatible'; compatCaveat?: string | null }) | null;
};

export function BuildRow({ buildSlug, vehicleId, categorySlug, categoryLabel, item }: Props) {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  return (
    <>
      <li className="hairline-soft-b py-4 px-5 grid grid-cols-12 gap-3 items-center row-hover">
        <span className="col-span-2 eyebrow text-fg-dim">{categoryLabel}</span>
        {item ? (
          <>
            <Link
              href={`/part/${partSlug(item.part.brand)}/${partSlug(item.part.model)}`}
              className="col-span-5 min-w-0 block"
            >
              <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">{item.part.brand}</span>
              <span className="display-md text-base text-fg leading-tight truncate block">{item.part.model}</span>
            </Link>
            <span className="col-span-2">
              {item.compatStatus && <CompatBadge status={item.compatStatus} caveat={item.compatCaveat} />}
            </span>
            <span className="col-span-2 figure text-right text-fg">{formatPrice(item.part.cheapestPriceCents)}</span>
            <span className="col-span-1 text-right">
              <button
                onClick={() => startTransition(() => removeItemAction({ slug: buildSlug, partId: item.part.id }))}
                disabled={pending}
                className="text-fg-dim hover:text-danger text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)]"
                title="Remove from build"
              >
                ×
              </button>
            </span>
          </>
        ) : (
          <>
            <span className="col-span-7 italic text-fg-dim text-sm">— empty</span>
            <span className="col-span-2 text-right">
              <button onClick={() => setOpen(true)} className="btn-ghost py-1.5">+ ADD</button>
            </span>
            <span className="col-span-1" />
          </>
        )}
      </li>
      <PartPickerModal
        open={open}
        onClose={() => setOpen(false)}
        buildSlug={buildSlug}
        vehicleId={vehicleId}
        categorySlug={categorySlug}
        categoryLabel={categoryLabel}
      />
    </>
  );
}
```

### Step 2.9: Build page wires it all together

```tsx
// app/build/[slug]/page.tsx
import { notFound } from 'next/navigation';
import { getBuild } from '@/lib/queries/builds';
import { listCategoriesWithCounts } from '@/lib/queries/parts';
import { listCategoryPartsRankedForVehicle, type CompatStatus } from '@/lib/queries/compat';
import { SiteHeader } from '@/app/components/site-header';
import { SiteFooter } from '@/app/components/site-footer';
import { BuildRow } from '@/app/components/build-row';
import { BuildSummary } from '@/app/components/build-summary';

export const dynamic = 'force-dynamic';

export default async function BuildPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const build = await getBuild(slug);
  if (!build) return notFound();

  const allCategories = await listCategoriesWithCounts();

  // for each part in the build, compute its compat status
  const compatByPart: Record<number, { status: CompatStatus; caveat: string | null }> = {};
  for (const it of build.items) {
    const ranked = await listCategoryPartsRankedForVehicle({
      categorySlug: it.part.categorySlug,
      vehicleId: build.vehicle.id,
    });
    const found = ranked.find((p) => p.id === it.part.id);
    if (found) compatByPart[it.part.id] = { status: found.status, caveat: found.caveat };
  }

  // bucket items by category
  const itemsByCategory = new Map<string, typeof build.items[number]>();
  for (const it of build.items) itemsByCategory.set(it.part.categorySlug, it);

  return (
    <>
      <SiteHeader crumbs={[{ label: 'build', href: '/parts' }, { label: slug }]} />
      <main className="mx-auto max-w-[1400px] px-6 py-12 flex-1">
        <p className="eyebrow-signal mb-3">[BUILD] · {slug}</p>
        <h1 className="display-lg">
          {build.vehicle.year} {build.vehicle.make} {build.vehicle.model}
          {build.vehicle.subModel ? ' ' + build.vehicle.subModel : ''}
          <span className="text-signal">.</span>
        </h1>
        <p className="body-sm mt-2">
          {build.vehicle.trim ? build.vehicle.trim + ' · ' : ''}
          {build.vehicle.generation} chassis
        </p>

        <div className="mt-10 grid grid-cols-12 gap-8">
          <div className="col-span-12 lg:col-span-8">
            <ul className="hairline">
              {allCategories.map((c) => {
                const it = itemsByCategory.get(c.slug);
                const itemWithCompat = it
                  ? {
                      ...it,
                      compatStatus: compatByPart[it.part.id]?.status ?? 'unknown',
                      compatCaveat: compatByPart[it.part.id]?.caveat ?? null,
                    }
                  : null;
                return (
                  <BuildRow
                    key={c.slug}
                    buildSlug={slug}
                    vehicleId={build.vehicle.id}
                    categorySlug={c.slug}
                    categoryLabel={c.name}
                    item={itemWithCompat}
                  />
                );
              })}
            </ul>
          </div>
          <aside className="col-span-12 lg:col-span-4">
            <BuildSummary build={build} />
          </aside>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
```

### Step 2.10: Verify and commit

```bash
npm test
npm run build
```

Manual: visit `/`, pick a vehicle, START BUILD → modal opens on a row → search/click adds → row updates with the part + compat badge.

```bash
git add -A
git commit -m "feat(builds): build editor with category rows, part picker modal, server actions, compat badges"
```

---

## Task 3: Affiliate redirector

**What you're building:** `/go/[listingId]` route that looks up the listing, appends the vendor's affiliate param, logs the click, and 302-redirects. Buy buttons throughout the site (catalog, part detail, build summary) point at this URL instead of the raw vendor link.

**Files:**
- Create: `app/go/[listingId]/route.ts`
- Modify: `app/part/[brand]/[model]/page.tsx` — change the buy buttons to `/go/[id]`
- (Optional) Add an integration test that hits the route and asserts headers + click row inserted

### Step 3.1: Implement the route

```ts
// app/go/[listingId]/route.ts
import { NextRequest } from 'next/server';
import { db } from '@/lib/db/client';
import { vendorListings, vendors, affiliateClicks } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { createHash } from 'node:crypto';

function hashIp(ip: string): string {
  return createHash('sha256').update(ip).digest('hex').slice(0, 32);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ listingId: string }> },
) {
  const { listingId } = await params;
  const id = Number(listingId);
  if (!id || Number.isNaN(id)) return Response.json({ error: 'bad listing id' }, { status: 400 });

  const [row] = await db
    .select({
      listingId: vendorListings.id,
      partId: vendorListings.partId,
      vendorId: vendorListings.vendorId,
      vendorUrl: vendorListings.vendorUrl,
      affiliateParam: vendors.affiliateParam,
      affiliateValue: vendors.affiliateValue,
    })
    .from(vendorListings)
    .innerJoin(vendors, eq(vendors.id, vendorListings.vendorId))
    .where(eq(vendorListings.id, id))
    .limit(1);
  if (!row) return Response.json({ error: 'not found' }, { status: 404 });

  // build outbound URL with affiliate code attached if known
  let target: URL;
  try {
    target = new URL(row.vendorUrl);
  } catch {
    return Response.json({ error: 'invalid vendor url' }, { status: 500 });
  }
  if (row.affiliateParam && row.affiliateValue) {
    target.searchParams.set(row.affiliateParam, row.affiliateValue);
  }

  // log click (fire-and-forget; don't block redirect on a slow insert)
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ?? '0.0.0.0';
  const ua = req.headers.get('user-agent') ?? null;
  const buildSlug = req.nextUrl.searchParams.get('build');
  void db.insert(affiliateClicks).values({
    listingId: row.listingId,
    partId: row.partId,
    vendorId: row.vendorId,
    buildId: buildSlug ? null : null, // resolving slug→id is fine to skip in v1; phase 2 can add it
    ipHash: hashIp(ip),
    userAgent: ua,
  }).catch((e) => console.error('[/go] click log failed', e));

  return Response.redirect(target.toString(), 302);
}
```

### Step 3.2: Update buy buttons

In `app/part/[brand]/[model]/page.tsx`, change the BUY @ button anchor and the per-row vendor anchors to point at `/go/${l.listingId}` instead of the raw `l.vendorUrl`.

### Step 3.3: Commit

```bash
git add -A
git commit -m "feat(redirect): /go/[listingId] affiliate redirector with click logging"
```

---

## Task 4: SEO + 404 + error boundary + sitemap

**Files:**
- Create: `app/not-found.tsx`
- Create: `app/error.tsx`
- Create: `app/sitemap.ts`
- Create: `app/robots.ts`
- Modify: `app/layout.tsx` — add OpenGraph metadata
- Add per-page metadata exports in catalog/category/part-detail/build pages

### Step 4.1: 404 page

```tsx
// app/not-found.tsx
import Link from 'next/link';
import { SiteHeader } from '@/app/components/site-header';
import { SiteFooter } from '@/app/components/site-footer';

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex-1 mx-auto max-w-[1400px] px-6 py-32 text-center">
        <p className="eyebrow-signal mb-4">[404] · LOST IN THE PIT</p>
        <h1 className="display-xl">Wrong way<span className="text-signal">.</span></h1>
        <p className="body mt-6 max-w-md mx-auto">
          The route doesn&apos;t exist or the part isn&apos;t indexed yet.
        </p>
        <div className="mt-10 flex items-center gap-4 justify-center">
          <Link href="/" className="btn-primary">RETURN TO PIT</Link>
          <Link href="/parts" className="arrow-link">Browse catalog</Link>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
```

### Step 4.2: Error boundary

```tsx
// app/error.tsx
'use client';

import Link from 'next/link';

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <html>
      <body className="min-h-screen bg-bg text-fg flex flex-col items-center justify-center px-6 text-center">
        <p className="eyebrow text-danger">[ERR] · UNEXPECTED FAULT</p>
        <h1 className="display-lg mt-4">Something broke<span className="text-signal">.</span></h1>
        <p className="body mt-3 font-[family-name:var(--font-mono)] text-sm text-fg-muted max-w-xl">
          {error.message || 'Unknown error'}
        </p>
        <div className="mt-8 flex gap-4">
          <button onClick={() => reset()} className="btn-primary">RETRY</button>
          <Link href="/" className="arrow-link">Home</Link>
        </div>
      </body>
    </html>
  );
}
```

### Step 4.3: Sitemap

```ts
// app/sitemap.ts
import type { MetadataRoute } from 'next';
import { listCategoriesWithCounts, listAllParts } from '@/lib/queries/parts';
import { partSlug } from '@/lib/format';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000';
  const [categories, allParts] = await Promise.all([listCategoriesWithCounts(), listAllParts()]);
  return [
    { url: `${base}/`, changeFrequency: 'weekly', priority: 1 },
    { url: `${base}/parts`, changeFrequency: 'daily', priority: 0.9 },
    ...categories.map((c) => ({ url: `${base}/parts/${c.slug}`, changeFrequency: 'weekly' as const, priority: 0.7 })),
    ...allParts.map((p) => ({
      url: `${base}/part/${partSlug(p.brand)}/${partSlug(p.model)}`,
      changeFrequency: 'weekly' as const,
      priority: 0.6,
    })),
  ];
}
```

### Step 4.4: Robots

```ts
// app/robots.ts
import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000';
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: ['/api/', '/build/'] },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
```

### Step 4.5: OpenGraph metadata

Update `app/layout.tsx` `metadata`:

```ts
export const metadata: Metadata = {
  title: { default: 'CarPartPicker', template: '%s · CarPartPicker' },
  description: 'PCPartPicker for tuner cars. Compatibility-checked mod builds with affiliate buy-through.',
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  openGraph: {
    title: 'CarPartPicker',
    description: 'PCPartPicker for tuner cars.',
    type: 'website',
  },
};
```

### Step 4.6: Commit

```bash
git add -A
git commit -m "feat(seo): 404 page, error boundary, sitemap, robots, OG metadata"
```

---

## Final verification

```bash
npm test                  # all tests passing
npm run build             # clean build
npm run test:e2e          # Playwright still green (selectors may need updates)
```

Push the branch:

```bash
git push origin phase-1-mvp
```

Smoke test in the browser:
1. Visit `/` → vehicle picker visible
2. Pick 2018 WRX Premium → click START BUILD
3. Land on `/build/<slug>` with the vehicle name in the header
4. Click + ADD on Intake → modal opens, search works, parts ranked by compat
5. Click a part → row updates with compat badge
6. Click a part name → goes to `/part/[brand]/[model]`
7. On part detail, click BUY → `/go/<id>` redirects to vendor with affiliate code
8. Visit any bogus URL → branded 404 page
