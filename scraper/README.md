# CarPartPicker — Scraper

Python service that scrapes mod retailers and upserts normalized parts into Postgres.

## Layout

```
scraper/
├── src/scraper/
│   ├── normalized.py             # NormalizedPart, WheelSpecs, TireSpecs (pydantic)
│   ├── fitment_parser.py         # Regex parser for vendor fitment prose
│   ├── category_map.py           # YAML-backed vendor->our taxonomy mapping
│   ├── upsert.py                 # Idempotent Postgres writer
│   ├── orchestrator.py           # Runs vendors, post-processes, upserts
│   ├── db.py                     # psycopg connection
│   ├── __main__.py               # CLI entry point: python -m scraper <vendor>
│   └── vendors/
│       └── fcp_euro.py           # First vendor; one parser per vendor
├── tests/
│   ├── conftest.py               # Loads .env.local for DATABASE_URL
│   ├── fixtures/<vendor>/        # Captured HTML, used by parser tests
│   └── test_*.py                 # 19 tests
├── category_map.yaml             # Vendor category strings -> our slugs
└── pyproject.toml
```

## Running

```bash
# install deps
uv sync --all-groups

# unit + integration tests (requires DATABASE_URL in repo .env.local)
uv run pytest

# live scrape against FCP Euro (~75 fetches at 1 req/s)
uv run python -m scraper fcp-euro

# one-shot from fixtures (no network)
uv run python -c "
from scraper.orchestrator import run_vendor_from_fixtures
from pathlib import Path
n = run_vendor_from_fixtures('fcp-euro', Path('tests/fixtures/fcp-euro'))
print(f'upserted {n} parts')
"
```

## Adding a vendor

1. Capture 3 representative HTML fixtures into `tests/fixtures/<slug>/`. Save from a real browser if the vendor has anti-bot (Cloudflare, Incapsula, etc.).
2. Write `src/scraper/vendors/<slug>.py` exposing:
   ```python
   def parse_category_page(html: str, *, base_url: str) -> list[str]: ...
   def parse_product_page(html: str, *, url: str) -> Optional[NormalizedPart]: ...
   ```
3. Add a vendor row in the TypeScript seed (`lib/db/seed/vendors.ts`).
4. Extend `category_map.yaml` with the vendor's category strings.
5. Add `tests/test_<slug>.py`.
6. Wire into `orchestrator.py`:
   - Add a branch to `run_vendor_from_fixtures` for the new slug.
   - Add a `_live_scrape_<slug>` async function with seed category URLs.
   - Add a branch to `run_vendor_live` for the new slug.

## Vendor reconnaissance findings (Phase 0)

- **Summit Racing** — DEFERRED. Imperva Incapsula blocks bot UAs at the product detail page level. Needs Playwright + stealth or a paid proxy. Reconsider in Phase 2.
- **FCP Euro** — Working. JSON-LD `Product` blocks on every PDP make parsing trivial.
- **ECS Tuning** — DEFERRED. Cloudflare interstitial against bot UAs. Same shape as Summit.
- **AmericanMuscle** — Reachable; not yet implemented (Mustang-only, lower priority for MVP).
- **RallySport Direct** — Reconnaissance was inconclusive (URL scheme not obvious). Worth revisiting with a manual category browse before declaring blocked.
- **eBay Motors** — Has an official Affiliate API; alternative path if scrape vendors continue to be blocked.

## Architecture rationale

- One module per vendor isolates HTML brittleness — a Summit redesign doesn't break FCP Euro.
- The orchestrator owns network concerns (rate limit, User-Agent, retries) so vendor modules stay pure parsers.
- Idempotent upsert keys on `(brand, model, sku)` (or `(brand, model, name)` when SKU is missing). Same part scraped twice doesn't duplicate; price refreshes update the listing in place.
- Fitment parsing is regex-only in Phase 0. Phase 2 adds a Haiku LLM fallback for messy strings.
