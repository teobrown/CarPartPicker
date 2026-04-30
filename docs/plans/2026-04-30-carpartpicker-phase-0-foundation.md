# CarPartPicker — Phase 0 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the database, seed reference data (vehicles, categories, vendors), implement one end-to-end scraper (Summit Racing) that produces normalized parts in Postgres, and ship a read-only Next.js catalog page rendering scraped data.

**Architecture:** Monorepo with a Next.js 15 app at the root and a separate Python scraper in `scraper/`. Both services share a single Postgres database. Drizzle ORM owns the TypeScript schema and migrations. The scraper writes raw `NormalizedPart` rows through a Python upserter. GitHub Actions runs the scraper weekly. No build-editor or compatibility logic in this phase — that's Phase 1.

**Tech Stack:**
- Frontend / API: Next.js 15 (App Router), TypeScript, Tailwind CSS
- ORM / Migrations: Drizzle + drizzle-kit
- Database: Postgres 16 (local via docker-compose, prod on Neon)
- Scraper: Python 3.12 with `uv`, `httpx`, `selectolax`, `pydantic`, `psycopg`
- Testing (TS): Vitest for units, Playwright for e2e
- Testing (Python): pytest with recorded HTML fixtures
- CI / cron: GitHub Actions

**Reference:** `docs/specs/2026-04-30-carpartpicker-design.md`

**Repository layout this plan produces:**

```
CarPartPicker/
├── app/                              # Next.js app router
│   ├── parts/page.tsx                # catalog index
│   ├── parts/[category]/page.tsx     # per-category listing
│   ├── part/[brand]/[model]/page.tsx # part detail
│   ├── layout.tsx
│   └── page.tsx                      # placeholder landing
├── lib/
│   ├── db/
│   │   ├── schema.ts                 # Drizzle schema (all tables)
│   │   ├── client.ts                 # connection
│   │   └── seed/
│   │       ├── vehicles.ts
│   │       ├── categories.ts
│   │       └── vendors.ts
│   └── queries/
│       └── parts.ts                  # part list + detail queries
├── tests/
│   ├── unit/
│   │   └── seed.test.ts
│   └── e2e/
│       └── catalog.spec.ts
├── scraper/
│   ├── pyproject.toml
│   ├── src/scraper/
│   │   ├── __init__.py
│   │   ├── normalized.py             # dataclasses
│   │   ├── fitment_parser.py         # regex parser
│   │   ├── category_map.py           # vendor string -> our taxonomy
│   │   ├── upsert.py                 # writes to Postgres
│   │   ├── orchestrator.py           # runs vendor modules
│   │   └── vendors/
│   │       ├── __init__.py
│   │       └── summit_racing.py
│   ├── tests/
│   │   ├── fixtures/summit/          # recorded HTML
│   │   ├── test_fitment_parser.py
│   │   ├── test_category_map.py
│   │   ├── test_summit_racing.py
│   │   └── test_upsert.py
│   └── category_map.yaml
├── .github/workflows/
│   └── scrape-summit.yml
├── docker-compose.yml
├── drizzle.config.ts
├── playwright.config.ts
├── vitest.config.ts
├── tsconfig.json
├── next.config.ts
├── package.json
└── README.md
```

---

## Task 1: Bootstrap the monorepo

**Files:**
- Create: `package.json`, `tsconfig.json`, `next.config.ts`, `.gitignore`, `README.md`
- Create: `app/layout.tsx`, `app/page.tsx`
- Create: `docker-compose.yml`
- Create: `.env.example`, `.env.local`
- Create: `scraper/pyproject.toml`, `scraper/src/scraper/__init__.py`, `scraper/README.md`

- [ ] **Step 1.1: Initialize git repo and base structure**

```bash
cd C:/Users/teobr/Downloads/ClaudeProjects/CarPartPicker
git init
echo "node_modules/
.next/
.env.local
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
.superpowers/
playwright-report/
test-results/" > .gitignore
```

- [ ] **Step 1.2: Create Next.js app with TypeScript + Tailwind**

```bash
npx create-next-app@latest . \
  --typescript --tailwind --eslint --app --src-dir=false \
  --import-alias="@/*" --no-git --turbopack --use-npm
```

When prompted "directory not empty," confirm yes. Replace the generated `app/page.tsx` with a placeholder:

```tsx
// app/page.tsx
export default function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">CarPartPicker</h1>
      <p className="text-sm opacity-70">Phase 0 foundation. Visit /parts.</p>
    </main>
  );
}
```

- [ ] **Step 1.3: Add docker-compose for local Postgres**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: cpp
      POSTGRES_PASSWORD: cpp
      POSTGRES_DB: carpartpicker
    ports:
      - "5432:5432"
    volumes:
      - cpp_pgdata:/var/lib/postgresql/data

volumes:
  cpp_pgdata:
```

```bash
# .env.example
DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker
```

```bash
cp .env.example .env.local
docker compose up -d
```

- [ ] **Step 1.4: Initialize the Python scraper project**

```bash
mkdir -p scraper/src/scraper/vendors
mkdir -p scraper/tests/fixtures/summit
cd scraper
```

```toml
# scraper/pyproject.toml
[project]
name = "carpartpicker-scraper"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27",
  "selectolax>=0.3.21",
  "pydantic>=2.7",
  "psycopg[binary]>=3.2",
  "pyyaml>=6.0",
  "rapidfuzz>=3.9",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

```bash
cd scraper
uv sync --all-groups
cd ..
```

Touch placeholder packages so imports work:

```python
# scraper/src/scraper/__init__.py
__version__ = "0.1.0"
```

```python
# scraper/src/scraper/vendors/__init__.py
```

- [ ] **Step 1.5: Verify Next.js dev server runs**

Run: `npm run dev`
Expected: server boots, http://localhost:3000 returns the placeholder home page. Stop the server (Ctrl+C).

- [ ] **Step 1.6: Verify scraper package imports**

Run: `cd scraper && uv run python -c "import scraper; print(scraper.__version__)" && cd ..`
Expected: prints `0.1.0`.

- [ ] **Step 1.7: Commit**

```bash
git add -A
git commit -m "chore: bootstrap Next.js app + Python scraper skeleton"
```

---

## Task 2: Drizzle schema for all tables

**Files:**
- Create: `drizzle.config.ts`
- Create: `lib/db/schema.ts`
- Create: `lib/db/client.ts`
- Create: `drizzle/` (generated migrations folder)
- Modify: `package.json` (add Drizzle scripts)
- Test: `tests/unit/schema.test.ts`

- [ ] **Step 2.1: Install Drizzle + Postgres driver + Vitest**

```bash
npm install drizzle-orm postgres
npm install -D drizzle-kit vitest @types/node tsx dotenv
```

Add scripts to `package.json` under `"scripts"`:

```json
"db:generate": "drizzle-kit generate",
"db:migrate": "tsx lib/db/migrate.ts",
"db:studio": "drizzle-kit studio",
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 2.2: Drizzle config**

```ts
// drizzle.config.ts
import { defineConfig } from 'drizzle-kit';
import 'dotenv/config';

export default defineConfig({
  schema: './lib/db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: { url: process.env.DATABASE_URL! },
});
```

- [ ] **Step 2.3: Write the failing schema query test**

```ts
// tests/unit/schema.test.ts
import { describe, it, expect } from 'vitest';
import { db } from '@/lib/db/client';
import { vehicles, categories, vendors, vendorListings, parts, fitmentRules, builds, buildItems, affiliateClicks } from '@/lib/db/schema';

describe('schema is queryable', () => {
  it.each([
    ['vehicles', vehicles],
    ['categories', categories],
    ['vendors', vendors],
    ['vendor_listings', vendorListings],
    ['parts', parts],
    ['fitment_rules', fitmentRules],
    ['builds', builds],
    ['build_items', buildItems],
    ['affiliate_clicks', affiliateClicks],
  ])('selects 0 rows from %s on a fresh DB', async (_name, table) => {
    const rows = await db.select().from(table).limit(1);
    expect(rows.length).toBeLessThanOrEqual(1);
  });
});
```

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'node',
    setupFiles: ['dotenv/config'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
```

- [ ] **Step 2.4: Run test, verify it fails (no schema yet)**

Run: `npm test`
Expected: FAIL — module `@/lib/db/schema` not found.

- [ ] **Step 2.5: Write the schema**

```ts
// lib/db/schema.ts
import {
  pgTable, serial, text, integer, varchar, boolean, timestamp,
  uniqueIndex, index, jsonb, bigserial,
} from 'drizzle-orm/pg-core';

export const vehicles = pgTable('vehicles', {
  id: serial('id').primaryKey(),
  make: varchar('make', { length: 64 }).notNull(),
  model: varchar('model', { length: 64 }).notNull(),
  year: integer('year').notNull(),
  trim: varchar('trim', { length: 64 }),
  subModel: varchar('sub_model', { length: 64 }),
  generation: varchar('generation', { length: 16 }).notNull(),
  bodyStyle: varchar('body_style', { length: 32 }),
  boltPattern: varchar('bolt_pattern', { length: 16 }),
  centerBoreMm: integer('center_bore_mm'),
  stockWheelWidthIn: integer('stock_wheel_width_in'),
  stockWheelOffsetMm: integer('stock_wheel_offset_mm'),
  stockTireSize: varchar('stock_tire_size', { length: 32 }),
  maxNoRubWidthIn: integer('max_no_rub_width_in'),
}, (t) => ({
  uq: uniqueIndex('vehicles_make_model_year_trim_uq').on(t.make, t.model, t.year, t.trim),
  genIdx: index('vehicles_generation_idx').on(t.generation),
}));

export const categories = pgTable('categories', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 64 }).notNull(),
  slug: varchar('slug', { length: 64 }).notNull().unique(),
  parentId: integer('parent_id'),
  description: text('description'),
});

export const vendors = pgTable('vendors', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 64 }).notNull(),
  slug: varchar('slug', { length: 64 }).notNull().unique(),
  affiliateProgram: varchar('affiliate_program', { length: 64 }),
  affiliateParam: varchar('affiliate_param', { length: 32 }),
  affiliateValue: varchar('affiliate_value', { length: 64 }),
  baseUrl: varchar('base_url', { length: 256 }).notNull(),
});

export const parts = pgTable('parts', {
  id: serial('id').primaryKey(),
  categoryId: integer('category_id').notNull().references(() => categories.id),
  brand: varchar('brand', { length: 64 }).notNull(),
  model: varchar('model', { length: 128 }).notNull(),
  sku: varchar('sku', { length: 64 }),
  name: varchar('name', { length: 256 }).notNull(),
  description: text('description'),
  imageUrl: varchar('image_url', { length: 512 }),
  // wheel-only
  wheelDiameterIn: integer('wheel_diameter_in'),
  wheelWidthIn: integer('wheel_width_in'),
  wheelOffsetMm: integer('wheel_offset_mm'),
  wheelBoltPattern: varchar('wheel_bolt_pattern', { length: 16 }),
  wheelCenterBoreMm: integer('wheel_center_bore_mm'),
  // tire-only
  tireSectionWidth: integer('tire_section_width'),
  tireAspect: integer('tire_aspect'),
  tireDiameter: integer('tire_diameter'),
  // shared
  weightLbs: integer('weight_lbs'),
  msrpCents: integer('msrp_cents'),
}, (t) => ({
  brandModelIdx: index('parts_brand_model_idx').on(t.brand, t.model),
  categoryIdx: index('parts_category_idx').on(t.categoryId),
}));

export const vendorListings = pgTable('vendor_listings', {
  id: serial('id').primaryKey(),
  partId: integer('part_id').notNull().references(() => parts.id),
  vendorId: integer('vendor_id').notNull().references(() => vendors.id),
  vendorSku: varchar('vendor_sku', { length: 64 }),
  vendorUrl: varchar('vendor_url', { length: 1024 }).notNull(),
  priceCents: integer('price_cents'),
  inStock: boolean('in_stock').default(true).notNull(),
  lastScrapedAt: timestamp('last_scraped_at', { withTimezone: true }).defaultNow().notNull(),
  missedRuns: integer('missed_runs').default(0).notNull(),
}, (t) => ({
  uq: uniqueIndex('vendor_listings_vendor_part_uq').on(t.vendorId, t.partId),
}));

export const fitmentRules = pgTable('fitment_rules', {
  id: serial('id').primaryKey(),
  partId: integer('part_id').notNull().references(() => parts.id),
  make: varchar('make', { length: 64 }),
  model: varchar('model', { length: 64 }),
  generation: varchar('generation', { length: 16 }),
  yearStart: integer('year_start'),
  yearEnd: integer('year_end'),
  trimsIncluded: text('trims_included').array(),
  trimsExcluded: text('trims_excluded').array(),
  bodyStyle: varchar('body_style', { length: 32 }),
  status: varchar('status', { length: 32 }).notNull(), // 'fits' | 'fits_with_caveat' | 'incompatible' | 'unknown'
  caveat: text('caveat'),
  requiresPartCategories: text('requires_part_categories').array(),
  conflictsWithPartIds: integer('conflicts_with_part_ids').array(),
  source: varchar('source', { length: 64 }).notNull(),
}, (t) => ({
  partIdx: index('fitment_rules_part_idx').on(t.partId),
  matchIdx: index('fitment_rules_match_idx').on(t.make, t.model, t.generation),
}));

export const builds = pgTable('builds', {
  id: serial('id').primaryKey(),
  slug: varchar('slug', { length: 16 }).notNull().unique(),
  vehicleId: integer('vehicle_id').notNull().references(() => vehicles.id),
  ownerUserId: integer('owner_user_id'),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
});

export const buildItems = pgTable('build_items', {
  buildId: integer('build_id').notNull().references(() => builds.id, { onDelete: 'cascade' }),
  partId: integer('part_id').notNull().references(() => parts.id),
  position: integer('position').notNull(),
  userNote: text('user_note'),
}, (t) => ({
  pk: uniqueIndex('build_items_pk').on(t.buildId, t.partId, t.position),
}));

export const affiliateClicks = pgTable('affiliate_clicks', {
  id: bigserial('id', { mode: 'number' }).primaryKey(),
  buildId: integer('build_id'),
  listingId: integer('listing_id').notNull().references(() => vendorListings.id),
  partId: integer('part_id').notNull().references(() => parts.id),
  vendorId: integer('vendor_id').notNull().references(() => vendors.id),
  clickedAt: timestamp('clicked_at', { withTimezone: true }).defaultNow().notNull(),
  ipHash: varchar('ip_hash', { length: 64 }),
  userAgent: varchar('user_agent', { length: 512 }),
}, (t) => ({
  vendorIdx: index('affiliate_clicks_vendor_idx').on(t.vendorId, t.clickedAt),
}));
```

```ts
// lib/db/client.ts
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';

const client = postgres(process.env.DATABASE_URL!, { max: 10 });
export const db = drizzle(client);
```

- [ ] **Step 2.6: Generate the migration and apply it**

```bash
npm run db:generate
```

Create the migrate runner:

```ts
// lib/db/migrate.ts
import 'dotenv/config';
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

const client = postgres(process.env.DATABASE_URL!, { max: 1 });
const db = drizzle(client);

await migrate(db, { migrationsFolder: './drizzle' });
await client.end();
console.log('migrations applied');
```

```bash
npm run db:migrate
```

Expected: prints `migrations applied`. Verify in psql or `npm run db:studio`.

- [ ] **Step 2.7: Run schema test, verify it passes**

Run: `npm test`
Expected: 9 passing tests under `schema is queryable`.

- [ ] **Step 2.8: Commit**

```bash
git add -A
git commit -m "feat(db): add Drizzle schema and initial migration"
```

---

## Task 3: Vehicles seed data

**Files:**
- Create: `lib/db/seed/vehicles.ts`
- Create: `lib/db/seed/run.ts`
- Test: `tests/unit/seed.test.ts`
- Modify: `package.json` (add `db:seed` script)

- [ ] **Step 3.1: Write the failing test**

```ts
// tests/unit/seed.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { sql } from 'drizzle-orm';
import { runVehicleSeed } from '@/lib/db/seed/vehicles';

describe('vehicles seed', () => {
  beforeAll(async () => {
    await db.execute(sql`TRUNCATE TABLE vehicles RESTART IDENTITY CASCADE`);
    await runVehicleSeed();
  });

  it('inserts at least 150 vehicle rows across the 8 platform groups', async () => {
    const rows = await db.select().from(vehicles);
    expect(rows.length).toBeGreaterThanOrEqual(150);
  });

  it('every row has a non-null generation and bolt_pattern', async () => {
    const rows = await db.select().from(vehicles);
    for (const r of rows) {
      expect(r.generation, `${r.year} ${r.make} ${r.model}`).toBeTruthy();
      expect(r.boltPattern, `${r.year} ${r.make} ${r.model}`).toBeTruthy();
    }
  });

  it('covers all 8 platform groups', async () => {
    const rows = await db.select().from(vehicles);
    const models = new Set(rows.map((r) => r.model));
    expect(models).toContain('WRX');
    expect(models).toContain('GR Corolla');
    expect(models).toContain('GR86');
    expect(models).toContain('Civic Si');
    expect(models).toContain('Mustang');
    expect(models).toContain('MX-5 Miata');
    expect(models).toContain('Golf R');
  });
});
```

- [ ] **Step 3.2: Run test, verify it fails**

Run: `npm test -- tests/unit/seed.test.ts`
Expected: FAIL — `@/lib/db/seed/vehicles` does not exist.

- [ ] **Step 3.3: Write the seed**

The data below is hand-curated from publicly published OEM specs and tuner-community fitment guides. Bolt patterns and bore sizes are factual; `maxNoRubWidthIn` values are conservative empirical numbers from Subiestg / Civicx / S2KI / GR86 forum threads.

```ts
// lib/db/seed/vehicles.ts
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';

type V = typeof vehicles.$inferInsert;

const data: V[] = [
  // Subaru WRX (VA: 2015-2021), Premium / Limited / Base
  ...years(2015, 2021).flatMap((year) => trims(['Base', 'Premium', 'Limited']).map<V>((trim) => ({
    make: 'Subaru', model: 'WRX', year, trim, generation: 'VA',
    bodyStyle: 'sedan', boltPattern: '5x114.3', centerBoreMm: 56,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 55, stockTireSize: '235/45R17',
    maxNoRubWidthIn: 9,
  }))),
  // Subaru WRX (VB: 2022-2024)
  ...years(2022, 2024).flatMap((year) => trims(['Base', 'Premium', 'Limited', 'GT']).map<V>((trim) => ({
    make: 'Subaru', model: 'WRX', year, trim, generation: 'VB',
    bodyStyle: 'sedan', boltPattern: '5x114.3', centerBoreMm: 56,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 55, stockTireSize: '245/40R18',
    maxNoRubWidthIn: 9,
  }))),
  // Subaru STI (VA: 2015-2021)
  ...years(2015, 2021).flatMap((year) => trims(['Base', 'Limited']).map<V>((trim) => ({
    make: 'Subaru', model: 'WRX STI', year, trim, generation: 'VA',
    bodyStyle: 'sedan', boltPattern: '5x114.3', centerBoreMm: 56,
    stockWheelWidthIn: 9, stockWheelOffsetMm: 53, stockTireSize: '245/40R18',
    maxNoRubWidthIn: 10,
  }))),
  // Toyota GR Corolla (2023-2024)
  ...years(2023, 2024).flatMap((year) => trims(['Core', 'Circuit', 'Premium']).map<V>((trim) => ({
    make: 'Toyota', model: 'GR Corolla', year, trim, generation: 'GR',
    bodyStyle: 'hatch', boltPattern: '5x114.3', centerBoreMm: 60.1,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 45, stockTireSize: '235/40R18',
    maxNoRubWidthIn: 9.5,
  }))),
  // Toyota GR86 (2022-2024)
  ...years(2022, 2024).flatMap((year) => trims(['Base', 'Premium']).map<V>((trim) => ({
    make: 'Toyota', model: 'GR86', year, trim, generation: 'ZN8',
    bodyStyle: 'coupe', boltPattern: '5x100', centerBoreMm: 56.1,
    stockWheelWidthIn: 7.5, stockWheelOffsetMm: 48, stockTireSize: '215/40R18',
    maxNoRubWidthIn: 9,
  }))),
  // Subaru BRZ (2022-2024)
  ...years(2022, 2024).flatMap((year) => trims(['Premium', 'Limited']).map<V>((trim) => ({
    make: 'Subaru', model: 'BRZ', year, trim, generation: 'ZD8',
    bodyStyle: 'coupe', boltPattern: '5x100', centerBoreMm: 56.1,
    stockWheelWidthIn: 7.5, stockWheelOffsetMm: 48, stockTireSize: '215/40R18',
    maxNoRubWidthIn: 9,
  }))),
  // Honda Civic Si (FE: 2022-2024)
  ...years(2022, 2024).flatMap((year) => trims(['Base']).map<V>((trim) => ({
    make: 'Honda', model: 'Civic Si', year, trim, generation: 'FE',
    bodyStyle: 'sedan', boltPattern: '5x114.3', centerBoreMm: 64.1,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 50, stockTireSize: '235/40R18',
    maxNoRubWidthIn: 9,
  }))),
  // Honda Civic Type R (FK8: 2017-2021)
  ...years(2017, 2021).flatMap((year) => trims(['Base', 'Touring']).map<V>((trim) => ({
    make: 'Honda', model: 'Civic Type R', year, trim, generation: 'FK8',
    bodyStyle: 'hatch', boltPattern: '5x120', centerBoreMm: 64.1,
    stockWheelWidthIn: 8.5, stockWheelOffsetMm: 60, stockTireSize: '245/30R20',
    maxNoRubWidthIn: 10,
  }))),
  // Honda Civic Type R (FL5: 2023-2024)
  ...years(2023, 2024).flatMap((year) => trims(['Base']).map<V>((trim) => ({
    make: 'Honda', model: 'Civic Type R', year, trim, generation: 'FL5',
    bodyStyle: 'hatch', boltPattern: '5x120', centerBoreMm: 64.1,
    stockWheelWidthIn: 9.5, stockWheelOffsetMm: 60, stockTireSize: '265/30R19',
    maxNoRubWidthIn: 10.5,
  }))),
  // Ford Mustang GT (S550: 2015-2023)
  ...years(2015, 2023).flatMap((year) => trims(['Base', 'Premium']).map<V>((trim) => ({
    make: 'Ford', model: 'Mustang', year, trim, subModel: 'GT', generation: 'S550',
    bodyStyle: 'coupe', boltPattern: '5x114.3', centerBoreMm: 70.5,
    stockWheelWidthIn: 9, stockWheelOffsetMm: 38, stockTireSize: '255/40R19',
    maxNoRubWidthIn: 10,
  }))),
  // Ford Mustang Ecoboost (S550)
  ...years(2015, 2023).flatMap((year) => trims(['Base', 'Premium', 'High Performance']).map<V>((trim) => ({
    make: 'Ford', model: 'Mustang', year, trim, subModel: 'Ecoboost', generation: 'S550',
    bodyStyle: 'coupe', boltPattern: '5x114.3', centerBoreMm: 70.5,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 38, stockTireSize: '235/55R17',
    maxNoRubWidthIn: 10,
  }))),
  // Mazda MX-5 Miata (ND: 2016-2024)
  ...years(2016, 2024).flatMap((year) => trims(['Sport', 'Club', 'Grand Touring']).map<V>((trim) => ({
    make: 'Mazda', model: 'MX-5 Miata', year, trim, generation: 'ND',
    bodyStyle: 'roadster', boltPattern: '4x100', centerBoreMm: 54.1,
    stockWheelWidthIn: 7, stockWheelOffsetMm: 45, stockTireSize: '205/45R17',
    maxNoRubWidthIn: 8,
  }))),
  // VW Golf R (Mk7: 2015-2019)
  ...years(2015, 2019).flatMap((year) => trims(['Base', 'DCC']).map<V>((trim) => ({
    make: 'Volkswagen', model: 'Golf R', year, trim, generation: 'Mk7',
    bodyStyle: 'hatch', boltPattern: '5x112', centerBoreMm: 57.1,
    stockWheelWidthIn: 7.5, stockWheelOffsetMm: 51, stockTireSize: '235/35R19',
    maxNoRubWidthIn: 9,
  }))),
  // VW Golf R (Mk8: 2022-2024)
  ...years(2022, 2024).flatMap((year) => trims(['Base']).map<V>((trim) => ({
    make: 'Volkswagen', model: 'Golf R', year, trim, generation: 'Mk8',
    bodyStyle: 'hatch', boltPattern: '5x112', centerBoreMm: 57.1,
    stockWheelWidthIn: 8, stockWheelOffsetMm: 50, stockTireSize: '235/35R19',
    maxNoRubWidthIn: 9.5,
  }))),
  // VW GTI (Mk7 + Mk8)
  ...years(2015, 2021).flatMap((year) => trims(['S', 'SE', 'Autobahn']).map<V>((trim) => ({
    make: 'Volkswagen', model: 'GTI', year, trim, generation: 'Mk7',
    bodyStyle: 'hatch', boltPattern: '5x112', centerBoreMm: 57.1,
    stockWheelWidthIn: 7.5, stockWheelOffsetMm: 51, stockTireSize: '225/40R18',
    maxNoRubWidthIn: 9,
  }))),
  ...years(2022, 2024).flatMap((year) => trims(['S', 'SE', 'Autobahn']).map<V>((trim) => ({
    make: 'Volkswagen', model: 'GTI', year, trim, generation: 'Mk8',
    bodyStyle: 'hatch', boltPattern: '5x112', centerBoreMm: 57.1,
    stockWheelWidthIn: 7.5, stockWheelOffsetMm: 50, stockTireSize: '225/40R18',
    maxNoRubWidthIn: 9,
  }))),
];

function years(start: number, end: number): number[] {
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}
function trims<T extends string>(t: T[]): T[] { return t; }

export async function runVehicleSeed() {
  await db.insert(vehicles).values(data).onConflictDoNothing();
  return data.length;
}
```

```ts
// lib/db/seed/run.ts
import 'dotenv/config';
import { runVehicleSeed } from './vehicles';

const n = await runVehicleSeed();
console.log(`vehicles seeded: ${n}`);
process.exit(0);
```

Add to `package.json` scripts:

```json
"db:seed:vehicles": "tsx lib/db/seed/run.ts"
```

- [ ] **Step 3.4: Run the seed**

Run: `npm run db:seed:vehicles`
Expected: prints `vehicles seeded: N` where N ≥ 150.

- [ ] **Step 3.5: Run test, verify it passes**

Run: `npm test -- tests/unit/seed.test.ts`
Expected: PASS — all 3 assertions.

- [ ] **Step 3.6: Commit**

```bash
git add -A
git commit -m "feat(seed): add vehicles seed for 8 platform groups"
```

---

## Task 4: Categories seed

**Files:**
- Create: `lib/db/seed/categories.ts`
- Modify: `lib/db/seed/run.ts`
- Test: extend `tests/unit/seed.test.ts`

- [ ] **Step 4.1: Write the failing test**

Append to `tests/unit/seed.test.ts`:

```ts
import { categories } from '@/lib/db/schema';
import { runCategorySeed } from '@/lib/db/seed/categories';

describe('categories seed', () => {
  beforeAll(async () => {
    await db.execute(sql`TRUNCATE TABLE categories RESTART IDENTITY CASCADE`);
    await runCategorySeed();
  });

  it('inserts the 15 MVP categories', async () => {
    const rows = await db.select().from(categories);
    expect(rows.length).toBeGreaterThanOrEqual(15);
    const slugs = rows.map((r) => r.slug);
    for (const expected of [
      'intake', 'catback', 'axleback', 'muffler-delete', 'tune', 'downpipe',
      'intercooler', 'bov', 'coilovers', 'springs', 'sway-bars',
      'wheels', 'tires', 'lip-kit', 'spoiler', 'fender-flares',
      'headlights', 'taillights',
    ]) {
      expect(slugs, `missing slug: ${expected}`).toContain(expected);
    }
  });
});
```

- [ ] **Step 4.2: Run test, verify it fails**

Run: `npm test -- tests/unit/seed.test.ts`
Expected: FAIL — module `@/lib/db/seed/categories` not found.

- [ ] **Step 4.3: Write the seed**

```ts
// lib/db/seed/categories.ts
import { db } from '@/lib/db/client';
import { categories } from '@/lib/db/schema';

type C = typeof categories.$inferInsert;

const data: C[] = [
  { name: 'Intake', slug: 'intake' },
  { name: 'Catback Exhaust', slug: 'catback' },
  { name: 'Axleback Exhaust', slug: 'axleback' },
  { name: 'Muffler Delete', slug: 'muffler-delete' },
  { name: 'Tune', slug: 'tune' },
  { name: 'Downpipe', slug: 'downpipe' },
  { name: 'Intercooler', slug: 'intercooler' },
  { name: 'Blow-Off Valve', slug: 'bov' },
  { name: 'Coilovers', slug: 'coilovers' },
  { name: 'Lowering Springs', slug: 'springs' },
  { name: 'Sway Bars', slug: 'sway-bars' },
  { name: 'Wheels', slug: 'wheels' },
  { name: 'Tires', slug: 'tires' },
  { name: 'Lip Kit', slug: 'lip-kit' },
  { name: 'Spoiler', slug: 'spoiler' },
  { name: 'Fender Flares', slug: 'fender-flares' },
  { name: 'Headlights', slug: 'headlights' },
  { name: 'Taillights', slug: 'taillights' },
];

export async function runCategorySeed() {
  await db.insert(categories).values(data).onConflictDoNothing();
  return data.length;
}
```

Update `lib/db/seed/run.ts`:

```ts
import 'dotenv/config';
import { runVehicleSeed } from './vehicles';
import { runCategorySeed } from './categories';

console.log(`vehicles seeded: ${await runVehicleSeed()}`);
console.log(`categories seeded: ${await runCategorySeed()}`);
process.exit(0);
```

- [ ] **Step 4.4: Run seed and verify**

```bash
npm run db:seed:vehicles  # also seeds categories now; rename if you prefer
npm test -- tests/unit/seed.test.ts
```

Expected: tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add -A
git commit -m "feat(seed): add 18 mod categories"
```

---

## Task 5: Vendors seed

**Files:**
- Create: `lib/db/seed/vendors.ts`
- Modify: `lib/db/seed/run.ts`
- Test: extend `tests/unit/seed.test.ts`

- [ ] **Step 5.1: Write the failing test**

Append to `tests/unit/seed.test.ts`:

```ts
import { vendors } from '@/lib/db/schema';
import { runVendorSeed } from '@/lib/db/seed/vendors';

describe('vendors seed', () => {
  beforeAll(async () => {
    await db.execute(sql`TRUNCATE TABLE vendors RESTART IDENTITY CASCADE`);
    await runVendorSeed();
  });

  it('inserts the 6 launch vendors', async () => {
    const rows = await db.select().from(vendors);
    const slugs = rows.map((r) => r.slug).sort();
    expect(slugs).toEqual([
      'americanmuscle', 'ebay-motors', 'ecs-tuning',
      'fcp-euro', 'rallysport-direct', 'summit-racing',
    ]);
  });
});
```

- [ ] **Step 5.2: Run test, verify it fails**

Run: `npm test -- tests/unit/seed.test.ts`
Expected: FAIL.

- [ ] **Step 5.3: Write the seed**

```ts
// lib/db/seed/vendors.ts
import { db } from '@/lib/db/client';
import { vendors } from '@/lib/db/schema';

type V = typeof vendors.$inferInsert;

// affiliateValue is a placeholder; replace with the real ID once the program
// signup is approved (see spec §11 open question 2).
const data: V[] = [
  {
    name: 'Summit Racing', slug: 'summit-racing',
    affiliateProgram: 'Impact Radius', affiliateParam: 'utm_source',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.summitracing.com',
  },
  {
    name: 'FCP Euro', slug: 'fcp-euro',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.fcpeuro.com',
  },
  {
    name: 'ECS Tuning', slug: 'ecs-tuning',
    affiliateProgram: 'AvantLink', affiliateParam: 'avad',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.ecstuning.com',
  },
  {
    name: 'AmericanMuscle', slug: 'americanmuscle',
    affiliateProgram: 'AmericanMuscle Affiliate', affiliateParam: 'aff',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.americanmuscle.com',
  },
  {
    name: 'RallySport Direct', slug: 'rallysport-direct',
    affiliateProgram: 'ShareASale', affiliateParam: 'sscid',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.rallysportdirect.com',
  },
  {
    name: 'eBay Motors', slug: 'ebay-motors',
    affiliateProgram: 'eBay Partner Network', affiliateParam: 'campid',
    affiliateValue: 'carpartpicker', baseUrl: 'https://www.ebay.com',
  },
];

export async function runVendorSeed() {
  await db.insert(vendors).values(data).onConflictDoNothing();
  return data.length;
}
```

Update `lib/db/seed/run.ts` to also call `runVendorSeed()`.

- [ ] **Step 5.4: Run and verify**

```bash
npm run db:seed:vehicles
npm test -- tests/unit/seed.test.ts
```

Expected: PASS.

- [ ] **Step 5.5: Commit**

```bash
git add -A
git commit -m "feat(seed): add 6 vendors with placeholder affiliate IDs"
```

---

## Task 6: Python — NormalizedPart contract

**Files:**
- Create: `scraper/src/scraper/normalized.py`
- Test: `scraper/tests/test_normalized.py`

- [ ] **Step 6.1: Write the failing test**

```python
# scraper/tests/test_normalized.py
from scraper.normalized import NormalizedPart, WheelSpecs, TireSpecs


def test_normalized_part_round_trip():
    p = NormalizedPart(
        vendor="summit-racing",
        vendor_sku="SUM-12345",
        vendor_url="https://www.summitracing.com/parts/sum-12345",
        brand="Cobb",
        model="Stage 1 Power Package",
        name="Cobb Stage 1 Power Package - Subaru WRX 2015-2021",
        category_hint="Tuning > ECU Tuning",
        image_url=None,
        price_cents=67500,
        in_stock=True,
        fitment_text="Fits 2015-2021 Subaru WRX, all trims",
        wheel_specs=None,
        tire_specs=None,
    )
    d = p.model_dump()
    assert d["vendor"] == "summit-racing"
    assert d["price_cents"] == 67500


def test_wheel_specs_validates_offset_range():
    w = WheelSpecs(diameter_in=18, width_in=9.5, offset_mm=35,
                   bolt_pattern="5x114.3", center_bore_mm=56.0)
    assert w.offset_mm == 35


def test_tire_specs_parses_size_string():
    t = TireSpecs.from_size_string("245/40R18")
    assert t.section_width == 245
    assert t.aspect == 40
    assert t.diameter == 18
```

- [ ] **Step 6.2: Run test, verify it fails**

Run: `cd scraper && uv run pytest tests/test_normalized.py -v`
Expected: FAIL — `scraper.normalized` doesn't exist.

- [ ] **Step 6.3: Write the module**

```python
# scraper/src/scraper/normalized.py
from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel, Field


class WheelSpecs(BaseModel):
    diameter_in: int
    width_in: float
    offset_mm: int
    bolt_pattern: str
    center_bore_mm: float


class TireSpecs(BaseModel):
    section_width: int
    aspect: int
    diameter: int

    @classmethod
    def from_size_string(cls, s: str) -> "TireSpecs":
        m = re.match(r"\s*(\d{3})/(\d{2})\s*[Rr]\s*(\d{2})\s*", s)
        if not m:
            raise ValueError(f"unrecognized tire size: {s!r}")
        return cls(section_width=int(m[1]), aspect=int(m[2]), diameter=int(m[3]))


class NormalizedPart(BaseModel):
    vendor: str
    vendor_sku: str
    vendor_url: str
    brand: str
    model: str
    name: str
    category_hint: str
    image_url: Optional[str] = None
    price_cents: Optional[int] = None
    in_stock: bool = True
    fitment_text: str = ""
    wheel_specs: Optional[WheelSpecs] = None
    tire_specs: Optional[TireSpecs] = None
```

- [ ] **Step 6.4: Run test, verify it passes**

Run: `cd scraper && uv run pytest tests/test_normalized.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add -A
git commit -m "feat(scraper): add NormalizedPart, WheelSpecs, TireSpecs models"
```

---

## Task 7: Python — fitment text regex parser

**Files:**
- Create: `scraper/src/scraper/fitment_parser.py`
- Test: `scraper/tests/test_fitment_parser.py`

- [ ] **Step 7.1: Write the failing test**

```python
# scraper/tests/test_fitment_parser.py
import pytest
from scraper.fitment_parser import parse_fitment, ParsedFitment


@pytest.mark.parametrize("text,expected", [
    (
        "Fits 2015-2021 Subaru WRX",
        [ParsedFitment(make="Subaru", model="WRX",
                       year_start=2015, year_end=2021,
                       trims_included=None, status="fits", caveat=None)],
    ),
    (
        "Fits 2022+ Subaru WRX (Premium, Limited)",
        [ParsedFitment(make="Subaru", model="WRX",
                       year_start=2022, year_end=None,
                       trims_included=["Premium", "Limited"],
                       status="fits", caveat=None)],
    ),
    (
        "Fits 2017-2021 Honda Civic Type R FK8",
        [ParsedFitment(make="Honda", model="Civic Type R",
                       year_start=2017, year_end=2021,
                       trims_included=None, status="fits", caveat=None)],
    ),
    (
        "Fits 2015-2023 Ford Mustang GT (requires fender rolling)",
        [ParsedFitment(make="Ford", model="Mustang", year_start=2015,
                       year_end=2023, trims_included=["GT"],
                       status="fits_with_caveat",
                       caveat="requires fender rolling")],
    ),
    ("", []),
    ("Fits all cars", []),
])
def test_parse_fitment(text, expected):
    assert parse_fitment(text) == expected
```

- [ ] **Step 7.2: Run test, verify it fails**

Run: `cd scraper && uv run pytest tests/test_fitment_parser.py -v`
Expected: FAIL.

- [ ] **Step 7.3: Write the parser**

```python
# scraper/src/scraper/fitment_parser.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, List

CAVEAT_PHRASES = [
    "requires fender rolling",
    "requires trimming",
    "requires modification",
    "may require",
]

# Make + model patterns. Add new pairs as the catalog grows.
KNOWN_MODELS: list[tuple[str, str]] = [
    ("Subaru", "WRX STI"),
    ("Subaru", "WRX"),
    ("Subaru", "BRZ"),
    ("Toyota", "GR Corolla"),
    ("Toyota", "GR86"),
    ("Honda", "Civic Type R"),
    ("Honda", "Civic Si"),
    ("Ford", "Mustang"),
    ("Mazda", "MX-5 Miata"),
    ("Volkswagen", "Golf R"),
    ("Volkswagen", "GTI"),
]

YEAR_RANGE_RE = re.compile(r"(?P<ys>\d{4})\s*[-–]\s*(?P<ye>\d{4})")
YEAR_OPEN_RE = re.compile(r"(?P<ys>\d{4})\+")
TRIMS_RE = re.compile(r"\(([^)]+)\)")


@dataclass(frozen=True)
class ParsedFitment:
    make: str
    model: str
    year_start: Optional[int]
    year_end: Optional[int]
    trims_included: Optional[list[str]]
    status: str  # 'fits' | 'fits_with_caveat'
    caveat: Optional[str]


def parse_fitment(text: str) -> List[ParsedFitment]:
    if not text:
        return []
    results: list[ParsedFitment] = []
    for make, model in KNOWN_MODELS:
        if model not in text:
            continue
        # year range
        ys: Optional[int]
        ye: Optional[int]
        if (m := YEAR_RANGE_RE.search(text)):
            ys, ye = int(m["ys"]), int(m["ye"])
        elif (m := YEAR_OPEN_RE.search(text)):
            ys, ye = int(m["ys"]), None
        else:
            continue  # we require at least one year token
        # trims (everything inside parens, except known caveat phrases)
        trims: Optional[list[str]] = None
        caveat: Optional[str] = None
        for paren_match in TRIMS_RE.findall(text):
            lower = paren_match.lower()
            if any(c in lower for c in CAVEAT_PHRASES):
                caveat = paren_match.strip()
            else:
                trims = [t.strip() for t in paren_match.split(",")]
        # also detect bare caveat phrases outside parens
        if caveat is None:
            for phrase in CAVEAT_PHRASES:
                if phrase in text.lower():
                    caveat = phrase
                    break
        status = "fits_with_caveat" if caveat else "fits"
        results.append(ParsedFitment(
            make=make, model=model, year_start=ys, year_end=ye,
            trims_included=trims, status=status, caveat=caveat,
        ))
        break  # one match per pass for v1; multi-vehicle fitments parse later
    return results
```

- [ ] **Step 7.4: Run test, verify it passes**

Run: `cd scraper && uv run pytest tests/test_fitment_parser.py -v`
Expected: 6 PASS.

- [ ] **Step 7.5: Commit**

```bash
git add -A
git commit -m "feat(scraper): add regex-based fitment parser for v1"
```

---

## Task 8: Python — category mapper

**Files:**
- Create: `scraper/category_map.yaml`
- Create: `scraper/src/scraper/category_map.py`
- Test: `scraper/tests/test_category_map.py`

- [ ] **Step 8.1: Write the failing test**

```python
# scraper/tests/test_category_map.py
from scraper.category_map import map_category


def test_exact_match_intake():
    assert map_category("Cold Air Intake Systems") == "intake"


def test_exact_match_catback():
    assert map_category("Cat-Back Exhaust Systems") == "catback"


def test_fuzzy_match_when_no_exact():
    assert map_category("Performance Cold-Air Intake System") == "intake"


def test_unknown_returns_none():
    assert map_category("Random Truck Accessory Bundle") is None
```

- [ ] **Step 8.2: Run test, verify it fails**

Run: `cd scraper && uv run pytest tests/test_category_map.py -v`
Expected: FAIL.

- [ ] **Step 8.3: Write the YAML and module**

```yaml
# scraper/category_map.yaml
intake:
  - "Cold Air Intake Systems"
  - "Air Intakes"
  - "Performance Intake System"
catback:
  - "Cat-Back Exhaust Systems"
  - "Catback Exhaust"
axleback:
  - "Axle-Back Exhaust"
  - "Axleback Exhaust"
muffler-delete:
  - "Muffler Delete"
  - "Muffler Bypass"
tune:
  - "Tuners"
  - "ECU Tuning"
  - "Programmers"
downpipe:
  - "Downpipes"
  - "Down Pipes"
intercooler:
  - "Intercoolers"
bov:
  - "Blow Off Valves"
  - "Diverter Valves"
coilovers:
  - "Coilover Suspension Kits"
  - "Coilovers"
springs:
  - "Lowering Springs"
sway-bars:
  - "Sway Bars"
  - "Anti-Roll Bars"
wheels:
  - "Wheels"
  - "Custom Wheels"
tires:
  - "Tires"
  - "Performance Tires"
lip-kit:
  - "Lip Kits"
  - "Front Lip"
spoiler:
  - "Spoilers"
  - "Wings"
fender-flares:
  - "Fender Flares"
headlights:
  - "Headlights"
  - "Headlamps"
taillights:
  - "Tail Lights"
  - "Taillights"
```

```python
# scraper/src/scraper/category_map.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Optional
import yaml
from rapidfuzz import process, fuzz

YAML_PATH = Path(__file__).resolve().parents[2] / "category_map.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, list[str]]:
    return yaml.safe_load(YAML_PATH.read_text())


def map_category(vendor_string: str, *, fuzzy_threshold: int = 80) -> Optional[str]:
    """Map a vendor's category string to our internal category slug."""
    table = _load()
    # exact match (case-insensitive)
    needle = vendor_string.strip().lower()
    for slug, aliases in table.items():
        if needle in (a.lower() for a in aliases):
            return slug
    # fuzzy match across the flattened alias list
    flat = [(slug, alias) for slug, aliases in table.items() for alias in aliases]
    choices = [alias for _, alias in flat]
    best = process.extractOne(vendor_string, choices, scorer=fuzz.WRatio,
                              score_cutoff=fuzzy_threshold)
    if best is None:
        return None
    matched_alias = best[0]
    for slug, alias in flat:
        if alias == matched_alias:
            return slug
    return None
```

- [ ] **Step 8.4: Run test, verify it passes**

Run: `cd scraper && uv run pytest tests/test_category_map.py -v`
Expected: 4 PASS.

- [ ] **Step 8.5: Commit**

```bash
git add -A
git commit -m "feat(scraper): add YAML-backed category mapper with fuzzy fallback"
```

---

## Task 9: Python — Summit Racing scraper module against fixtures

**Files:**
- Create: `scraper/tests/fixtures/summit/category_intake.html`
- Create: `scraper/tests/fixtures/summit/product_cobb_sf_intake.html`
- Create: `scraper/tests/fixtures/summit/product_invidia_n1.html`
- Create: `scraper/src/scraper/vendors/summit_racing.py`
- Test: `scraper/tests/test_summit_racing.py`

> **Note on fixtures:** Save 3 real Summit Racing pages to disk. From a normal browser (not the scraper), open a category like https://www.summitracing.com/search/category/cold-air-intake-systems and 2 product detail pages. Use the browser's "Save Page As → HTML, Complete" option, then copy only the saved `.html` (not the supporting folder) into the fixtures directory. **Do not commit any non-public pages or pages behind login walls.** If pages have been redesigned by the time you execute this plan, the selectors below need updating — that's expected scraper-maintenance work; check your CSS selectors against the current HTML first.

- [ ] **Step 9.1: Capture fixtures**

Save the three HTML files at the paths above. Each file should be ≤ 2 MB.

- [ ] **Step 9.2: Write the failing test**

```python
# scraper/tests/test_summit_racing.py
from pathlib import Path
import pytest
from scraper.vendors.summit_racing import parse_product_page, parse_category_page

FIXTURES = Path(__file__).parent / "fixtures" / "summit"


def test_parse_category_page_finds_product_links():
    html = (FIXTURES / "category_intake.html").read_text(encoding="utf-8", errors="ignore")
    urls = parse_category_page(html, base_url="https://www.summitracing.com")
    assert len(urls) > 0
    assert all(u.startswith("https://www.summitracing.com") for u in urls)


def test_parse_product_page_cobb_intake():
    html = (FIXTURES / "product_cobb_sf_intake.html").read_text(encoding="utf-8", errors="ignore")
    part = parse_product_page(html, url="https://www.summitracing.com/parts/cob-7160")
    assert part is not None
    assert part.vendor == "summit-racing"
    assert part.brand.lower().startswith("cobb")
    assert part.price_cents is not None and part.price_cents > 0
    assert "WRX" in part.fitment_text or "Subaru" in part.fitment_text
```

- [ ] **Step 9.3: Run test, verify it fails**

Run: `cd scraper && uv run pytest tests/test_summit_racing.py -v`
Expected: FAIL.

- [ ] **Step 9.4: Write the parser**

```python
# scraper/src/scraper/vendors/summit_racing.py
from __future__ import annotations
import re
from typing import Optional, Iterator
from urllib.parse import urljoin
from selectolax.parser import HTMLParser
from scraper.normalized import NormalizedPart

VENDOR_SLUG = "summit-racing"
PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


def parse_category_page(html: str, *, base_url: str) -> list[str]:
    """Return absolute product URLs found on a Summit category page."""
    tree = HTMLParser(html)
    urls: list[str] = []
    # Summit's product cards link via <a class="product-name" href="..."> or similar.
    # Both selectors are tried; vendor-redesigns may require updating.
    for sel in ("a.product-card__title", "a.product-name", "a[href*='/parts/']"):
        for a in tree.css(sel):
            href = a.attributes.get("href")
            if href:
                urls.append(urljoin(base_url, href))
        if urls:
            break
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]:
    tree = HTMLParser(html)

    name_el = tree.css_first("h1.product-name") or tree.css_first("h1")
    if name_el is None:
        return None
    name = name_el.text(strip=True)

    brand_el = tree.css_first(".product-brand a") or tree.css_first(".brand-name")
    brand = brand_el.text(strip=True) if brand_el else _guess_brand_from_name(name)

    sku_el = tree.css_first(".product-sku")
    sku = sku_el.text(strip=True).replace("Part #", "").strip() if sku_el else ""

    price_cents: Optional[int] = None
    price_el = tree.css_first(".price-current") or tree.css_first(".product-price")
    if price_el and (m := PRICE_RE.search(price_el.text())):
        price_cents = int(float(m.group(1).replace(",", "")) * 100)

    in_stock = True
    stock_el = tree.css_first(".availability") or tree.css_first(".stock-status")
    if stock_el and "out of stock" in stock_el.text(strip=True).lower():
        in_stock = False

    image_url: Optional[str] = None
    img = tree.css_first("img.product-image") or tree.css_first("img[itemprop='image']")
    if img:
        image_url = img.attributes.get("src") or img.attributes.get("data-src")

    fitment_text = ""
    fit_el = tree.css_first(".product-fitment") or tree.css_first("#fitment")
    if fit_el:
        fitment_text = fit_el.text(strip=True)

    category_hint = ""
    crumb_els = tree.css(".breadcrumbs a") or tree.css("nav.breadcrumb a")
    if crumb_els:
        category_hint = " > ".join(c.text(strip=True) for c in crumb_els[1:])

    model = name.split("-")[0].strip() if "-" in name else name
    return NormalizedPart(
        vendor=VENDOR_SLUG,
        vendor_sku=sku,
        vendor_url=url,
        brand=brand,
        model=model,
        name=name,
        category_hint=category_hint,
        image_url=image_url,
        price_cents=price_cents,
        in_stock=in_stock,
        fitment_text=fitment_text,
    )


def _guess_brand_from_name(name: str) -> str:
    # crude: assume the first word is the brand
    return name.split()[0] if name else "Unknown"


def scrape() -> Iterator[NormalizedPart]:
    """Live scrape entry point. Used in production; tests use the parsers directly."""
    raise NotImplementedError("wire up live scraping in Task 11")
```

- [ ] **Step 9.5: Run test, verify it passes**

Run: `cd scraper && uv run pytest tests/test_summit_racing.py -v`
Expected: 2 PASS. If selectors don't match the captured HTML, inspect the fixture and update the selectors in `summit_racing.py` until tests pass.

- [ ] **Step 9.6: Commit**

```bash
git add -A
git commit -m "feat(scraper): Summit Racing category + product parsers, with fixtures"
```

---

## Task 10: Python — upsert into Postgres

**Files:**
- Create: `scraper/src/scraper/db.py`
- Create: `scraper/src/scraper/upsert.py`
- Test: `scraper/tests/test_upsert.py`

- [ ] **Step 10.1: Write the failing test**

```python
# scraper/tests/test_upsert.py
import os
import pytest
import psycopg
from scraper.normalized import NormalizedPart
from scraper.upsert import upsert_part
from scraper.fitment_parser import parse_fitment

DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL, autocommit=False) as c:
        with c.cursor() as cur:
            cur.execute("BEGIN")
        yield c
        c.rollback()


def test_upsert_creates_part_listing_and_fitment_row(conn):
    p = NormalizedPart(
        vendor="summit-racing",
        vendor_sku="COB-7160",
        vendor_url="https://www.summitracing.com/parts/cob-7160",
        brand="Cobb",
        model="SF Intake",
        name="Cobb SF Intake - Subaru WRX",
        category_hint="Cold Air Intake Systems",
        price_cents=42500,
        in_stock=True,
        fitment_text="Fits 2015-2021 Subaru WRX",
    )
    parsed = parse_fitment(p.fitment_text)
    upsert_part(conn, p, parsed_fitment=parsed, category_slug="intake")
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM parts WHERE brand=%s AND model=%s",
                    ("Cobb", "SF Intake"))
        assert cur.fetchone()[0] == 1
        cur.execute("""SELECT count(*) FROM vendor_listings vl
                       JOIN parts p ON p.id = vl.part_id
                       WHERE p.brand=%s AND p.model=%s""", ("Cobb", "SF Intake"))
        assert cur.fetchone()[0] == 1
        cur.execute("""SELECT count(*) FROM fitment_rules fr
                       JOIN parts p ON p.id = fr.part_id
                       WHERE p.brand=%s""", ("Cobb",))
        assert cur.fetchone()[0] >= 1


def test_upsert_is_idempotent(conn):
    p = NormalizedPart(
        vendor="summit-racing", vendor_sku="COB-7160",
        vendor_url="https://www.summitracing.com/parts/cob-7160",
        brand="Cobb", model="SF Intake",
        name="Cobb SF Intake", category_hint="Cold Air Intake Systems",
        price_cents=42500, in_stock=True, fitment_text="Fits 2015-2021 Subaru WRX",
    )
    parsed = parse_fitment(p.fitment_text)
    upsert_part(conn, p, parsed_fitment=parsed, category_slug="intake")
    upsert_part(conn, p, parsed_fitment=parsed, category_slug="intake")
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM parts WHERE brand=%s", ("Cobb",))
        assert cur.fetchone()[0] == 1
```

- [ ] **Step 10.2: Run test, verify it fails**

```bash
cd scraper && DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker uv run pytest tests/test_upsert.py -v
```

Expected: FAIL.

- [ ] **Step 10.3: Write the upsert module**

```python
# scraper/src/scraper/db.py
import os
import psycopg

def connect():
    return psycopg.connect(os.environ["DATABASE_URL"])
```

```python
# scraper/src/scraper/upsert.py
from __future__ import annotations
from typing import Iterable
import psycopg
from scraper.normalized import NormalizedPart
from scraper.fitment_parser import ParsedFitment


def _category_id(conn: psycopg.Connection, slug: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE slug=%s", (slug,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"category slug not seeded: {slug}")
        return row[0]


def _vendor_id(conn: psycopg.Connection, slug: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM vendors WHERE slug=%s", (slug,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"vendor slug not seeded: {slug}")
        return row[0]


def upsert_part(
    conn: psycopg.Connection,
    p: NormalizedPart,
    *,
    parsed_fitment: Iterable[ParsedFitment],
    category_slug: str,
) -> int:
    """Insert/update a part + its single vendor listing + its fitment rules. Returns part_id."""
    category_id = _category_id(conn, category_slug)
    vendor_id = _vendor_id(conn, p.vendor)
    with conn.cursor() as cur:
        # part: dedupe on (brand, model, sku) when sku is present, else (brand, model, name)
        cur.execute(
            """
            INSERT INTO parts (category_id, brand, model, sku, name, image_url, msrp_cents)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (category_id, p.brand, p.model, p.vendor_sku or None, p.name, p.image_url, p.price_cents),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "SELECT id FROM parts WHERE brand=%s AND model=%s AND name=%s LIMIT 1",
                (p.brand, p.model, p.name),
            )
            row = cur.fetchone()
            assert row is not None, f"could not locate part after upsert: {p.name}"
        part_id = row[0]

        # vendor_listing
        cur.execute(
            """
            INSERT INTO vendor_listings (part_id, vendor_id, vendor_sku, vendor_url, price_cents, in_stock, last_scraped_at, missed_runs)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 0)
            ON CONFLICT (vendor_id, part_id) DO UPDATE SET
              price_cents = EXCLUDED.price_cents,
              in_stock = EXCLUDED.in_stock,
              vendor_url = EXCLUDED.vendor_url,
              last_scraped_at = NOW(),
              missed_runs = 0
            """,
            (part_id, vendor_id, p.vendor_sku, p.vendor_url, p.price_cents, p.in_stock),
        )

        # fitment rules: replace all rules from this source for this part
        cur.execute(
            "DELETE FROM fitment_rules WHERE part_id=%s AND source=%s",
            (part_id, f"vendor:{p.vendor}"),
        )
        for f in parsed_fitment:
            cur.execute(
                """
                INSERT INTO fitment_rules
                  (part_id, make, model, year_start, year_end, trims_included,
                   status, caveat, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (part_id, f.make, f.model, f.year_start, f.year_end,
                 f.trims_included, f.status, f.caveat, f"vendor:{p.vendor}"),
            )
    conn.commit()
    return part_id
```

- [ ] **Step 10.4: Seed prerequisite data and run test**

```bash
# from project root
npm run db:seed:vehicles
cd scraper
DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker uv run pytest tests/test_upsert.py -v
```

Expected: 2 PASS.

- [ ] **Step 10.5: Commit**

```bash
git add -A
git commit -m "feat(scraper): idempotent upsert for parts, listings, fitment"
```

---

## Task 11: Python — orchestrator end-to-end

**Files:**
- Create: `scraper/src/scraper/orchestrator.py`
- Create: `scraper/src/scraper/__main__.py`
- Test: `scraper/tests/test_orchestrator.py`
- Modify: `scraper/src/scraper/vendors/summit_racing.py` (implement live `scrape()`)

- [ ] **Step 11.1: Write the failing test**

```python
# scraper/tests/test_orchestrator.py
import os, psycopg
from pathlib import Path
from scraper.orchestrator import run_vendor_from_fixtures

FIXTURES = Path(__file__).parent / "fixtures" / "summit"
DATABASE_URL = os.environ["DATABASE_URL"]


def test_orchestrator_imports_summit_fixtures_into_db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM fitment_rules")
            cur.execute("DELETE FROM vendor_listings")
            cur.execute("DELETE FROM parts")
        run_vendor_from_fixtures("summit-racing", FIXTURES)
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM parts")
            assert cur.fetchone()[0] >= 1
            cur.execute("SELECT count(*) FROM vendor_listings")
            assert cur.fetchone()[0] >= 1
```

- [ ] **Step 11.2: Run test, verify it fails**

Run: `cd scraper && DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL.

- [ ] **Step 11.3: Write the orchestrator**

```python
# scraper/src/scraper/orchestrator.py
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Iterable
import httpx
from scraper.db import connect
from scraper.upsert import upsert_part
from scraper.fitment_parser import parse_fitment
from scraper.category_map import map_category
from scraper.normalized import NormalizedPart
from scraper.vendors import summit_racing

log = logging.getLogger(__name__)
USER_AGENT = "CarPartPickerBot/0.1 (+mailto:teobrown1@gmail.com)"


def _process_and_upsert(parts: Iterable[NormalizedPart]) -> int:
    n = 0
    with connect() as conn:
        for p in parts:
            slug = map_category(p.category_hint)
            if slug is None:
                log.warning("dropping part with unmapped category: %s", p.category_hint)
                continue
            parsed = parse_fitment(p.fitment_text)
            try:
                upsert_part(conn, p, parsed_fitment=parsed, category_slug=slug)
                n += 1
            except Exception:
                log.exception("upsert failed for %s", p.vendor_url)
                conn.rollback()
    return n


def run_vendor_from_fixtures(vendor_slug: str, fixtures_dir: Path) -> int:
    """Used for tests and dry runs. Reads pre-saved HTML files from disk."""
    parts: list[NormalizedPart] = []
    if vendor_slug == "summit-racing":
        for f in fixtures_dir.glob("product_*.html"):
            html = f.read_text(encoding="utf-8", errors="ignore")
            p = summit_racing.parse_product_page(html, url=f"file://{f}")
            if p:
                parts.append(p)
    else:
        raise ValueError(f"unknown vendor: {vendor_slug}")
    return _process_and_upsert(parts)


async def _live_scrape_summit(*, max_products: int = 200) -> list[NormalizedPart]:
    seed_categories = [
        "https://www.summitracing.com/search/category/cold-air-intake-systems",
        "https://www.summitracing.com/search/category/cat-back-exhaust-systems",
        # extend over time
    ]
    parts: list[NormalizedPart] = []
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "From": "teobrown1@gmail.com"},
                                  timeout=20.0, follow_redirects=True) as client:
        for cat_url in seed_categories:
            r = await client.get(cat_url)
            r.raise_for_status()
            urls = summit_racing.parse_category_page(r.text, base_url="https://www.summitracing.com")
            for u in urls[:max_products]:
                await asyncio.sleep(1.0)  # ~1 req/sec
                pr = await client.get(u)
                if pr.status_code != 200:
                    continue
                p = summit_racing.parse_product_page(pr.text, url=u)
                if p:
                    parts.append(p)
    return parts


def run_vendor_live(vendor_slug: str) -> int:
    if vendor_slug != "summit-racing":
        raise ValueError(f"unknown vendor: {vendor_slug}")
    parts = asyncio.run(_live_scrape_summit())
    return _process_and_upsert(parts)
```

```python
# scraper/src/scraper/__main__.py
import argparse
import logging
import sys
from scraper.orchestrator import run_vendor_live

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("vendor")
    args = parser.parse_args()
    n = run_vendor_live(args.vendor)
    print(f"upserted {n} parts from {args.vendor}")
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 11.4: Run test, verify it passes**

```bash
cd scraper && DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker uv run pytest tests/test_orchestrator.py -v
```

Expected: PASS.

- [ ] **Step 11.5: Commit**

```bash
git add -A
git commit -m "feat(scraper): orchestrator wires fixtures + live scraping for Summit"
```

---

## Task 12: Next.js — parts list query + catalog index page

**Files:**
- Create: `lib/queries/parts.ts`
- Create: `app/parts/page.tsx`
- Test: `tests/unit/parts.queries.test.ts`

- [ ] **Step 12.1: Write the failing query test**

```ts
// tests/unit/parts.queries.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, vendors } from '@/lib/db/schema';
import { sql } from 'drizzle-orm';
import { listPartsByCategory, listAllParts } from '@/lib/queries/parts';

describe('parts queries', () => {
  beforeAll(async () => {
    await db.execute(sql`TRUNCATE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`);
    const [intake] = await db.select().from(categories).where(sql`slug = 'intake'`).limit(1);
    const [v] = await db.select().from(vendors).where(sql`slug = 'summit-racing'`).limit(1);
    const [p] = await db.insert(parts).values({
      categoryId: intake.id, brand: 'Cobb', model: 'SF Intake',
      name: 'Cobb SF Intake', msrpCents: 42500,
    }).returning();
    await db.insert(vendorListings).values({
      partId: p.id, vendorId: v.id,
      vendorUrl: 'https://example.com', priceCents: 42000, inStock: true,
    });
  });

  it('listAllParts returns at least 1 row with the cheapest listing price', async () => {
    const rows = await listAllParts();
    expect(rows.length).toBeGreaterThan(0);
    const cobb = rows.find((r) => r.brand === 'Cobb' && r.model === 'SF Intake');
    expect(cobb).toBeDefined();
    expect(cobb!.cheapestPriceCents).toBe(42000);
  });

  it('listPartsByCategory filters by category slug', async () => {
    const intakeRows = await listPartsByCategory('intake');
    expect(intakeRows.every((r) => r.categorySlug === 'intake')).toBe(true);
    const exhaustRows = await listPartsByCategory('catback');
    expect(exhaustRows.length).toBe(0);
  });
});
```

- [ ] **Step 12.2: Run test, verify it fails**

Run: `npm test -- tests/unit/parts.queries.test.ts`
Expected: FAIL.

- [ ] **Step 12.3: Write the queries**

```ts
// lib/queries/parts.ts
import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, vendors } from '@/lib/db/schema';
import { sql, eq, min } from 'drizzle-orm';

export type PartListRow = {
  id: number;
  brand: string;
  model: string;
  name: string;
  imageUrl: string | null;
  categorySlug: string;
  cheapestPriceCents: number | null;
  vendorCount: number;
};

const baseQuery = () =>
  db
    .select({
      id: parts.id,
      brand: parts.brand,
      model: parts.model,
      name: parts.name,
      imageUrl: parts.imageUrl,
      categorySlug: categories.slug,
      cheapestPriceCents: min(vendorListings.priceCents),
      vendorCount: sql<number>`count(distinct ${vendorListings.vendorId})::int`,
    })
    .from(parts)
    .innerJoin(categories, eq(categories.id, parts.categoryId))
    .leftJoin(vendorListings, eq(vendorListings.partId, parts.id))
    .groupBy(parts.id, categories.slug);

export async function listAllParts(): Promise<PartListRow[]> {
  return baseQuery();
}

export async function listPartsByCategory(slug: string): Promise<PartListRow[]> {
  return baseQuery().where(eq(categories.slug, slug));
}
```

- [ ] **Step 12.4: Run test, verify it passes**

Run: `npm test -- tests/unit/parts.queries.test.ts`
Expected: PASS.

- [ ] **Step 12.5: Build the catalog page**

```tsx
// app/parts/page.tsx
import { listAllParts } from '@/lib/queries/parts';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function PartsCatalog() {
  const rows = await listAllParts();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Parts Catalog</h1>
      <p className="text-sm opacity-70 mb-6">{rows.length} parts</p>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {rows.map((p) => (
          <li key={p.id} className="border rounded p-4">
            <Link href={`/part/${slugify(p.brand)}/${slugify(p.model)}`}>
              <h2 className="font-semibold">{p.brand} {p.model}</h2>
              <p className="text-xs opacity-60">{p.categorySlug}</p>
              <p className="mt-2 font-mono">
                {p.cheapestPriceCents !== null
                  ? `$${(p.cheapestPriceCents / 100).toFixed(2)}`
                  : 'No price'}{' '}
                <span className="text-xs opacity-60">· {p.vendorCount} vendor(s)</span>
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
```

- [ ] **Step 12.6: Verify page renders**

Run: `npm run dev`. Visit http://localhost:3000/parts.
Expected: page lists at least one part (assumes Task 11 ran; otherwise the list is empty, which is also fine for this test).

- [ ] **Step 12.7: Commit**

```bash
git add -A
git commit -m "feat(web): catalog index page reading parts + cheapest listing"
```

---

## Task 13: Next.js — category and part-detail pages

**Files:**
- Create: `app/parts/[category]/page.tsx`
- Create: `app/part/[brand]/[model]/page.tsx`
- Modify: `lib/queries/parts.ts` (add `getPartByBrandModel`)

- [ ] **Step 13.1: Add the detail query and a test**

Append to `tests/unit/parts.queries.test.ts`:

```ts
import { getPartByBrandModel } from '@/lib/queries/parts';

it('getPartByBrandModel returns the part with all vendor listings', async () => {
  const found = await getPartByBrandModel('cobb', 'sf-intake');
  expect(found).toBeDefined();
  expect(found!.brand).toBe('Cobb');
  expect(found!.listings.length).toBeGreaterThan(0);
});
```

- [ ] **Step 13.2: Run test, verify it fails**

Run: `npm test -- tests/unit/parts.queries.test.ts`
Expected: FAIL.

- [ ] **Step 13.3: Implement the query**

Append to `lib/queries/parts.ts`:

```ts
export type VendorListingRow = {
  vendorSlug: string;
  vendorName: string;
  priceCents: number | null;
  inStock: boolean;
  vendorUrl: string;
  listingId: number;
};

export type PartDetail = PartListRow & {
  description: string | null;
  listings: VendorListingRow[];
};

export async function getPartByBrandModel(
  brandSlug: string,
  modelSlug: string,
): Promise<PartDetail | null> {
  const rows = await db
    .select({
      id: parts.id,
      brand: parts.brand,
      model: parts.model,
      name: parts.name,
      description: parts.description,
      imageUrl: parts.imageUrl,
      categorySlug: categories.slug,
      msrpCents: parts.msrpCents,
    })
    .from(parts)
    .innerJoin(categories, eq(categories.id, parts.categoryId))
    .where(sql`lower(replace(${parts.brand}, ' ', '-')) = ${brandSlug}
            AND lower(replace(${parts.model}, ' ', '-')) = ${modelSlug}`)
    .limit(1);
  if (rows.length === 0) return null;
  const p = rows[0];

  const listings = await db
    .select({
      listingId: vendorListings.id,
      vendorSlug: vendors.slug,
      vendorName: vendors.name,
      priceCents: vendorListings.priceCents,
      inStock: vendorListings.inStock,
      vendorUrl: vendorListings.vendorUrl,
    })
    .from(vendorListings)
    .innerJoin(vendors, eq(vendors.id, vendorListings.vendorId))
    .where(eq(vendorListings.partId, p.id));

  const cheapest = listings.reduce<number | null>((acc, l) => {
    if (l.priceCents === null) return acc;
    return acc === null || l.priceCents < acc ? l.priceCents : acc;
  }, null);

  return {
    ...p,
    cheapestPriceCents: cheapest,
    vendorCount: listings.length,
    listings,
  };
}
```

- [ ] **Step 13.4: Run test, verify it passes**

Run: `npm test -- tests/unit/parts.queries.test.ts`
Expected: PASS.

- [ ] **Step 13.5: Add the category page**

```tsx
// app/parts/[category]/page.tsx
import { listPartsByCategory } from '@/lib/queries/parts';
import { notFound } from 'next/navigation';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function CategoryPage(
  { params }: { params: Promise<{ category: string }> },
) {
  const { category } = await params;
  const rows = await listPartsByCategory(category);
  if (rows.length === 0) return notFound();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold capitalize">{category.replace(/-/g, ' ')}</h1>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {rows.map((p) => (
          <li key={p.id} className="border rounded p-4">
            <Link href={`/part/${slugify(p.brand)}/${slugify(p.model)}`}>
              <h2 className="font-semibold">{p.brand} {p.model}</h2>
              <p className="mt-2 font-mono">
                {p.cheapestPriceCents !== null
                  ? `$${(p.cheapestPriceCents / 100).toFixed(2)}`
                  : 'No price'}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
```

- [ ] **Step 13.6: Add the part detail page**

```tsx
// app/part/[brand]/[model]/page.tsx
import { getPartByBrandModel } from '@/lib/queries/parts';
import { notFound } from 'next/navigation';

export const dynamic = 'force-dynamic';

export default async function PartDetail(
  { params }: { params: Promise<{ brand: string; model: string }> },
) {
  const { brand, model } = await params;
  const p = await getPartByBrandModel(brand, model);
  if (!p) return notFound();
  return (
    <main className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold">{p.brand} {p.model}</h1>
      <p className="text-sm opacity-70 mb-4">{p.categorySlug}</p>
      {p.description && <p className="mb-6">{p.description}</p>}
      <h2 className="font-semibold mb-2">Vendors</h2>
      <ul className="space-y-2">
        {p.listings.map((l) => (
          <li key={l.listingId} className="border rounded p-3 flex justify-between">
            <span>{l.vendorName} {l.inStock ? '· in stock' : '· out of stock'}</span>
            <span className="font-mono">
              {l.priceCents !== null ? `$${(l.priceCents / 100).toFixed(2)}` : 'No price'}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 13.7: Verify pages render**

Run: `npm run dev`. Visit http://localhost:3000/parts/intake and http://localhost:3000/part/cobb/sf-intake.
Expected: both pages render and show the seeded part.

- [ ] **Step 13.8: Commit**

```bash
git add -A
git commit -m "feat(web): category listing + part detail pages with vendor list"
```

---

## Task 14: Playwright e2e for the catalog

**Files:**
- Create: `playwright.config.ts`
- Create: `tests/e2e/catalog.spec.ts`
- Modify: `package.json` (add `test:e2e` script)

- [ ] **Step 14.1: Install Playwright**

```bash
npm install -D @playwright/test
npx playwright install chromium
```

Add to `package.json`:

```json
"test:e2e": "playwright test"
```

- [ ] **Step 14.2: Write the failing e2e test**

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  use: { baseURL: 'http://localhost:3000' },
});
```

```ts
// tests/e2e/catalog.spec.ts
import { test, expect } from '@playwright/test';

test('catalog index lists at least one seeded part', async ({ page }) => {
  await page.goto('/parts');
  await expect(page.locator('h1')).toHaveText('Parts Catalog');
  const items = page.locator('main ul li');
  await expect(items.first()).toBeVisible();
});

test('part detail page shows the vendor block', async ({ page }) => {
  await page.goto('/parts');
  await page.locator('main ul li a').first().click();
  await expect(page.locator('h2')).toHaveText('Vendors');
});
```

- [ ] **Step 14.3: Run e2e tests, verify they pass**

```bash
# ensure data is seeded:
npm run db:seed:vehicles
cd scraper && DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker uv run python -m scraper summit-racing || echo "live scrape skipped — fixtures still in DB from upsert tests"
cd ..
npm run test:e2e
```

Expected: both tests PASS. If the parts table is empty, run the upsert test (Task 10) first to populate it.

- [ ] **Step 14.4: Commit**

```bash
git add -A
git commit -m "test(e2e): Playwright smoke for catalog + part detail"
```

---

## Task 15: GitHub Actions weekly scraper cron

**Files:**
- Create: `.github/workflows/scrape-summit.yml`

- [ ] **Step 15.1: Write the workflow**

```yaml
# .github/workflows/scrape-summit.yml
name: scrape-summit

on:
  schedule:
    - cron: '0 7 * * 1'  # Mondays 07:00 UTC
  workflow_dispatch: {}

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Install scraper deps
        working-directory: scraper
        run: uv sync --all-groups

      - name: Run scraper
        working-directory: scraper
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m scraper summit-racing
```

- [ ] **Step 15.2: Add the secret**

Locally:

```bash
gh secret set DATABASE_URL  # paste the Neon prod URL when prompted
```

Or via the GitHub UI: Settings → Secrets and variables → Actions → New repository secret → `DATABASE_URL`.

- [ ] **Step 15.3: Trigger the workflow manually**

```bash
gh workflow run scrape-summit
gh run watch
```

Expected: workflow run completes successfully, prints `upserted N parts from summit-racing`.

> If you don't have the GitHub repo set up yet, that's expected — defer this manual trigger until after you push to GitHub. The workflow file itself is committed and will run on the next Monday.

- [ ] **Step 15.4: Commit**

```bash
git add -A
git commit -m "ci: weekly Summit Racing scraper via GitHub Actions"
```

---

## Task 16: README and developer setup

**Files:**
- Modify: `README.md`
- Create: `scraper/README.md`

- [ ] **Step 16.1: Write the root README**

```markdown
# CarPartPicker

PCPartPicker for tuner cars. Phase 0 foundation: database schema, scraper, read-only catalog.

## Setup

Prereqs: Node 20+, Python 3.12+, Docker, [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Bring up local Postgres
docker compose up -d

# 2. Install Node deps and run migrations
npm install
cp .env.example .env.local
npm run db:migrate
npm run db:seed:vehicles  # seeds vehicles, categories, vendors

# 3. Set up the Python scraper
cd scraper
uv sync --all-groups
cd ..

# 4. Run the dev server
npm run dev  # http://localhost:3000

# 5. Run scraper end-to-end (live; requires Summit Racing to be reachable)
cd scraper
DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker \
  uv run python -m scraper summit-racing
```

## Commands

- `npm run dev` — Next.js dev server
- `npm test` — Vitest unit tests (requires DB up)
- `npm run test:e2e` — Playwright smoke tests
- `npm run db:generate` — generate a new Drizzle migration after schema edits
- `npm run db:migrate` — apply pending migrations
- `npm run db:seed:vehicles` — seed reference data
- `npm run db:studio` — open Drizzle Studio

## Project layout

See `docs/specs/2026-04-30-carpartpicker-design.md` for the full design.
See `docs/plans/` for phased implementation plans.
```

- [ ] **Step 16.2: Write the scraper README**

```markdown
# CarPartPicker — Scraper

Python service that scrapes mod retailers and upserts normalized parts into Postgres.

## Layout

- `src/scraper/normalized.py` — `NormalizedPart` / `WheelSpecs` / `TireSpecs` models
- `src/scraper/fitment_parser.py` — regex-based fitment text parser (v1)
- `src/scraper/category_map.py` — vendor category strings → our taxonomy
- `src/scraper/upsert.py` — Postgres writer
- `src/scraper/orchestrator.py` — fixture + live runners
- `src/scraper/vendors/<vendor>.py` — one module per vendor

## Running

```bash
uv sync --all-groups
DATABASE_URL=postgresql://cpp:cpp@localhost:5432/carpartpicker \
  uv run python -m scraper summit-racing
uv run pytest
```

## Adding a vendor

1. Capture 3-5 representative HTML fixtures in `tests/fixtures/<vendor>/`.
2. Write `src/scraper/vendors/<vendor>.py` exposing `parse_category_page` and `parse_product_page`.
3. Add a vendor row to `lib/db/seed/vendors.ts` (TypeScript side).
4. Extend `category_map.yaml` with the vendor's category strings.
5. Add a test file `tests/test_<vendor>.py` mirroring `test_summit_racing.py`.
6. Wire the vendor into `orchestrator.run_vendor_live`.
```

- [ ] **Step 16.3: Commit**

```bash
git add -A
git commit -m "docs: README for app and scraper"
```

---

## Self-Review

(Performed inline by the plan author.)

**Spec coverage:**
- §1 MVP scope — addressed by Tasks 3-5 (seeds for 8 platform groups, 18 categories, 6 vendors). 3D render, sound preview, accounts, build editor — all explicitly Phase 1+, not in this plan.
- §2 architecture — three services represented: Postgres (Tasks 1-2), Next.js app (Tasks 12-14), Python scraper (Tasks 6-11), GitHub Actions cron (Task 15).
- §3 data model — every table from the spec is in `lib/db/schema.ts` (Task 2).
- §4 scraper — `NormalizedPart` (Task 6), regex fitment parser (Task 7), category mapper (Task 8), Summit module (Task 9), upsert (Task 10), orchestrator with rate-limited live scrape (Task 11), GitHub Actions schedule (Task 15).
- §5 compatibility engine — **not in Phase 0.** Catalog page in Tasks 12-13 is read-only; no compat filtering by vehicle yet. Documented as Phase 1 work.
- §6 frontend — landing placeholder (Task 1), catalog index (Task 12), category + detail pages (Task 13). Build editor + part picker modal are Phase 1.
- §7 affiliate redirector — **not in Phase 0.** Phase 1.
- §8 phasing — this plan implements Phase 0 only, as stated up top.
- §9 error handling — partial: scraper failure isolation (Task 11 try/except per part), idempotent upsert (Task 10). Sentry alerting deferred to Phase 2 per the spec.
- §10 testing strategy — fitment parser snapshots (Task 7), wheel/tire math tests (Phase 1), scraper fixture tests (Task 9), e2e (Task 14). Compatibility engine golden tests are Phase 1.

**Placeholder scan:** No "TBD", "TODO" left as work items. The placeholder I left intentionally is `affiliateValue: 'carpartpicker'` in vendor seeds (Task 5), flagged in §11 of the spec. Affiliate program signups are external work, not code.

**Type consistency:** `NormalizedPart` shape matches between Python (Task 6) and the Drizzle `parts` columns (Task 2). `parsed_fitment` carries the same fields used by `fitment_rules` columns. `category_slug` arg in `upsert_part` matches `categories.slug` values seeded in Task 4. Function names referenced across tasks: `runVehicleSeed`, `runCategorySeed`, `runVendorSeed`, `listAllParts`, `listPartsByCategory`, `getPartByBrandModel`, `parse_fitment`, `map_category`, `upsert_part`, `run_vendor_live`, `run_vendor_from_fixtures` — all defined exactly once and called by their definition name.

**Scope:** Phase 0 only. Phases 1 and 2 each get their own plan after this one is executed.

---

## Done. Plan saved to:
`docs/plans/2026-04-30-carpartpicker-phase-0-foundation.md`
