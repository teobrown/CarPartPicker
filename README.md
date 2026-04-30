# CarPartPicker

A "PCPartPicker for tuner cars" — a vehicle-aware aftermarket parts catalog with build planner.

This monorepo holds the Next.js web app (root) and the Python scraper service (`scraper/`).

## Stack

- **Web:** Next.js 16 (App Router, TypeScript, Tailwind) on Vercel
- **Database:** Postgres 16 — local Docker for dev, Neon for prod — accessed via Drizzle ORM
- **Scraper:** Python 3.12 with `httpx` + `selectolax` + `psycopg`, managed by `uv`

## Repo layout

```
.
├── app/                  # Next.js App Router pages
├── docs/
│   ├── specs/            # Product + technical specs
│   └── plans/            # Phase implementation plans
├── scraper/              # Python scraper service
│   ├── src/scraper/      # Package source
│   └── tests/            # Pytest tests + fixtures
├── docker-compose.yml    # Local Postgres
├── .env.example          # Template for .env.local
└── package.json
```

## Local development

### Prerequisites

- Node.js 20+ (via `nvm` or installer)
- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) for the Python service
- Docker Desktop (for local Postgres)

### Setup

```bash
# 1. Install Node deps
npm install

# 2. Start local Postgres
cp .env.example .env.local
docker compose up -d

# 3. Install Python deps for the scraper
cd scraper
uv sync --all-groups
cd ..

# 4. Run the dev server
npm run dev
```

Open <http://localhost:3000>.

## Roadmap

See `docs/specs/` for the product design and `docs/plans/` for the active implementation plan. Phase 0 (current) bootstraps the catalog with a single vendor (Summit Racing) and a hardcoded set of vehicles.
