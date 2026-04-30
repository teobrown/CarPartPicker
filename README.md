# CarPartPicker

PCPartPicker for tuner cars. Pick your make/model/year, get a compatibility-checked catalog of bolt-on, suspension, wheel, and body mods, and assemble a build with affiliate buy-through links.

**Phase 0 status:** Foundation. Database, seeds, FCP Euro scraper, and read-only catalog work. Compatibility engine, build editor, affiliate redirector, and additional vendors come in Phases 1-2.

See [`docs/specs/2026-04-30-carpartpicker-design.md`](docs/specs/2026-04-30-carpartpicker-design.md) for the full design and [`docs/plans/2026-04-30-carpartpicker-phase-0-foundation.md`](docs/plans/2026-04-30-carpartpicker-phase-0-foundation.md) for the Phase 0 implementation plan.

## Stack

- **Frontend / API:** Next.js 16 (App Router, Turbopack, TypeScript, Tailwind)
- **ORM / migrations:** Drizzle + drizzle-kit
- **Database:** Postgres on [Neon](https://neon.tech) (free tier)
- **Scraper:** Python 3.12 with `uv`, `httpx`, `selectolax`, `pydantic`, `psycopg`
- **Tests:** Vitest (units) + Playwright (e2e)
- **CI / cron:** GitHub Actions

## Setup

Prereqs: Node 20+, Python 3.12+, [`uv`](https://docs.astral.sh/uv/), a Postgres database (Neon recommended).

```bash
# 1. Clone and install Node deps
git clone https://github.com/teobrown/CarPartPicker.git
cd CarPartPicker
npm install

# 2. Configure DATABASE_URL
cp .env.example .env.local
# Edit .env.local — replace the local Docker default with your Neon URL.
# Free Neon project: https://console.neon.tech
# .env.local example:
#   DATABASE_URL=postgresql://owner:password@ep-xxx.aws.neon.tech/neondb?sslmode=require

# 3. Apply migrations
npm run db:migrate

# 4. Seed reference data (vehicles + categories + vendors)
npm run db:seed

# 5. Install Python scraper deps
cd scraper && uv sync --all-groups && cd ..

# 6. Run the dev server
npm run dev   # http://localhost:3000

# 7. Populate parts by running the scraper against FCP Euro fixtures
cd scraper
uv run python -c "
from scraper.orchestrator import run_vendor_from_fixtures
from pathlib import Path
n = run_vendor_from_fixtures('fcp-euro', Path('tests/fixtures/fcp-euro'))
print(f'upserted {n} parts')
"
cd ..

# 8. Visit http://localhost:3000/parts to see the catalog
```

For a real live scrape against FCP Euro's site (slower, ~75 product fetches over a minute):

```bash
cd scraper
uv run python -m scraper fcp-euro
```

## Common commands

| What | How |
|---|---|
| Dev server | `npm run dev` |
| Production build | `npm run build` |
| Unit tests | `npm test` (Vitest, 18 tests) |
| E2E tests | `npm run test:e2e` (Playwright, 2 tests) |
| Generate a migration after schema edits | `npm run db:generate` |
| Apply pending migrations | `npm run db:migrate` |
| Re-seed reference tables | `npm run db:seed` |
| Open Drizzle Studio (DB GUI) | `npm run db:studio` |
| Scraper unit tests | `cd scraper && uv run pytest` (19 tests) |
| Live scrape FCP Euro | `cd scraper && uv run python -m scraper fcp-euro` |

## Project layout

```
CarPartPicker/
├── app/                              # Next.js App Router
│   ├── parts/                        # /parts catalog index + /parts/[category]
│   ├── part/[brand]/[model]/         # Part detail page
│   ├── layout.tsx
│   └── page.tsx
├── lib/
│   ├── db/
│   │   ├── schema.ts                 # Drizzle schema (9 tables)
│   │   ├── client.ts                 # Connection
│   │   ├── migrate.ts                # Migration runner
│   │   └── seed/
│   │       ├── vehicles.ts           # 195 vehicles across 8 platform groups
│   │       ├── categories.ts         # 18 mod categories
│   │       ├── vendors.ts            # 6 launch vendors
│   │       └── run.ts                # Registry-based seed runner
│   └── queries/
│       └── parts.ts                  # listAllParts, listPartsByCategory, getPartByBrandModel
├── scraper/                          # Python service
│   ├── src/scraper/                  # Package
│   ├── tests/                        # pytest with HTML fixtures
│   ├── category_map.yaml             # vendor category strings -> our taxonomy
│   └── pyproject.toml
├── tests/
│   ├── unit/                         # Vitest
│   └── e2e/                          # Playwright
├── drizzle/                          # Generated migrations (committed)
├── .github/workflows/                # CI
└── docs/
    ├── specs/
    └── plans/
```

## Database

The schema is the source of truth in `lib/db/schema.ts`. Drizzle generates migrations into `drizzle/` — both schema and migrations are committed.

Cents are stored as `bigint` (so we can `SUM()` revenue without overflow). Wheel/tire dimensions and bore diameters use `numeric(p,s)` for exact decimal precision (no float drift). Anonymous build URLs use a slug (8-char nanoid) — see `builds.slug`.

The seeded `vehicles` table covers 8 platform groups (~12 chassis): WRX/STI (VA + VB), GR Corolla, GR86/BRZ, Civic Si/Type R (FK8 + FL5), Mustang GT/Ecoboost (S550), MX-5 (ND), Golf R/GTI (Mk7 + Mk8). Total ~195 rows across years and trims.

## Vendor scrapers

Phase 0 ships with one vendor: **FCP Euro**. The original plan led with Summit Racing, but reconnaissance found Summit's product detail pages are firewalled by Imperva Incapsula (4 KB JavaScript challenge instead of HTML). FCP Euro renders product data server-side via JSON-LD `Product` blocks, which is what the parser keys off.

Adding a new vendor:

1. Capture HTML fixtures: 1 category page + 2-3 product detail pages, saved to `scraper/tests/fixtures/<slug>/`.
2. Write `scraper/src/scraper/vendors/<slug_with_underscores>.py` exposing `parse_category_page` and `parse_product_page`.
3. Make sure `lib/db/seed/vendors.ts` lists the vendor with the right affiliate program / param / value (placeholders OK pre-launch).
4. Extend `scraper/category_map.yaml` with the vendor's category strings (the orchestrator's fuzzy fallback handles small differences).
5. Add `tests/test_<vendor>.py` mirroring `test_fcp_euro.py`.
6. Wire the vendor into `orchestrator.run_vendor_live` (and add a GitHub Actions workflow if you want a weekly cron).

## CI

`.github/workflows/scrape-fcp-euro.yml` runs the FCP Euro scraper every Monday at 07:00 UTC and on manual dispatch.

To enable:

1. Add the `DATABASE_URL` secret: `gh secret set DATABASE_URL` and paste the Neon URL.
2. Either merge this branch to `main` (GitHub only schedules workflows from the default branch) or trigger manually with `gh workflow run scrape-fcp-euro --ref <branch>`.

## What's not in Phase 0

- Build editor / compatibility engine (Phase 1)
- Affiliate redirector (Phase 1)
- Additional vendors beyond FCP Euro (Phase 2)
- 3D render of the configured car (deferred)
- Exhaust sound preview (deferred)

## License / status

Pre-launch. Internal project. Not yet open to contributions.
