# CarPartPicker — Design Spec

**Date:** 2026-04-30
**Owner:** Teo
**Working name:** CarPartPicker (rename before launch)
**Status:** Approved design, ready for implementation plan

---

## 1. Goal & Scope

A web app where someone with a tuner car picks their make/model/year/trim, gets a compatibility-checked catalog of bolt-on, suspension, wheel/tire, and body/aero/lighting mods, and assembles a build list with affiliate buy-through links. PCPartPicker, but for cars.

### MVP scope

- **8 platform groups at launch** (≈12 distinct chassis once siblings are split): WRX + STI, GR Corolla, GR86 + BRZ, Civic Si + Type R, Mustang GT, Mustang Ecoboost, MX-5, Golf R + GTI.
- **Tier 3 mod scope** — ~15 categories: Intake, Exhaust (Catback / Axleback / Muffler Delete), Tune, Downpipe, Intercooler, BOV, Coilovers, Springs, Sway Bars, Wheels, Tires, Lip Kit, Spoiler, Fender Flares, Headlights/Taillights.
- **Anonymous builds**, shareable URL (`/build/abc123`). Optional accounts later.
- **Live compatibility** shown as status badges (green ✓ fits / yellow ⚠ caveat / red ❌ incompatible / gray ? unknown).
- **Affiliate buy-through** to vendors (Summit Racing, FCP Euro, ECS Tuning, AmericanMuscle, RallySport Direct, eBay Motors).
- **Catalog freshness** ≤ 7 days stale via weekly scrapers.

### Out of scope (Phase 2/3+)

- 3D render of the configured car (kept as a *future* idea — too expensive for the team size).
- Exhaust sound preview library.
- Required user accounts.
- Build sharing / forks / social.
- Community-contributed fitment notes.
- Direct cart aggregation / multi-vendor checkout.

### Success criteria

1. A user with one of the 8 platforms can complete a 5-part build (intake, exhaust, tune, coilovers, wheels) end-to-end with all compat checks correct in under 5 minutes.
2. Affiliate clicks register and redirect to the right vendor with our affiliate code applied.
3. The catalog stays ≤ 7 days fresh per vendor without manual intervention.
4. Wheel/tire geometric fit math matches a published reference set within ±2mm tolerance.

---

## 2. System Architecture

Three independent services, one shared database. Each has one job; failure in one does not cascade.

```
┌─────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  Scraper Worker │──────▶│  Postgres (Neon) │◀──────│  Web App (Next.js)│
│  GitHub Actions │ writes│  parts, fitment, │ reads │  Vercel + API     │
│  cron weekly    │       │  builds, clicks  │       │  routes           │
└─────────────────┘       └──────────────────┘       └─────────┬────────┘
                                                                │
                                                                ▼
                                                      ┌──────────────────┐
                                                      │  /go/[listing]    │
                                                      │  affiliate redirect│
                                                      └──────────────────┘
```

### Services

- **Scraper Worker** — Python service. One module per vendor in `scraper/vendors/`. Runs on **GitHub Actions cron** (free, 6h job limit, weekly schedule). Writes to Postgres.
- **Postgres (Neon)** — single source of truth. Free tier sufficient for MVP traffic.
- **Web App (Next.js 15 on Vercel)** — server components for catalog (cached), client components for build editor. API routes for build CRUD, compatibility check, affiliate click logging, search.
- **Affiliate Redirector** — single Next.js route at `/go/[listing_id]`. Looks up vendor URL, appends affiliate parameter, logs click, 302 redirect. Sub-100ms.

### Why this shape

Each service can fail or redeploy independently. If a scraper breaks, catalog goes stale but the app stays up. Python in the scraper because parsing libraries (`httpx`, `selectolax`, `scrapy`) are stronger than Node equivalents. GitHub Actions for scraping because cron-with-secrets is built in and free.

---

## 3. Data Model

Two kinds of fitment: **categorical** (year/trim/generation match) and **geometric** (wheel offset, tire size, ride height clearance). Modeled separately.

```sql
-- Vehicles: every (make, model, year, trim, sub_model) combo we cover
vehicles(
  id, make, model, year, trim, sub_model,
  generation,                    -- chassis code: VA, VB, FK8, etc.
  body_style,                    -- sedan / hatch / coupe
  bolt_pattern,                  -- 5x100, 5x114.3, etc.
  center_bore_mm,
  stock_wheel_width_in, stock_wheel_offset_mm, stock_tire_size,
  max_no_rub_width_in            -- empirical max wheel width before fender rolling
)

-- Parts: one row per distinct part (across all vendors)
parts(
  id, category_id, brand, model, sku,
  name, description, image_url,
  -- wheel-only geometry
  wheel_diameter_in, wheel_width_in, wheel_offset_mm,
  wheel_bolt_pattern, wheel_center_bore_mm,
  -- tire-only geometry
  tire_section_width, tire_aspect, tire_diameter,
  -- shared
  weight_lbs, msrp_cents
)

categories(id, name, slug, parent_id, description)
-- Intake, Exhaust > Catback, Exhaust > Axleback, Tune, Coilovers, Wheels, Lip Kit, etc.

-- Vendor listings: same part may be sold by multiple vendors
vendors(id, name, slug, affiliate_program, affiliate_param, affiliate_value, base_url)
vendor_listings(id, part_id, vendor_id, vendor_url, price_cents, in_stock, last_scraped_at)

-- Fitment rules
fitment_rules(
  id, part_id,
  -- vehicle match (NULL = "any")
  make, model, generation, year_start, year_end,
  trims_included, trims_excluded, body_style,
  -- compatibility verdict
  status,                  -- 'fits' | 'fits_with_caveat' | 'incompatible' | 'unknown'
  caveat,                  -- "requires fender rolling"
  requires_part_categories,-- this part needs these categories already in the build
  conflicts_with_part_ids,
  source                   -- 'vendor:summit' | 'vendor:fcp' | 'manual' | 'community'
)

-- Builds: anonymous, slug-addressed
builds(id, slug, vehicle_id, created_at, updated_at, owner_user_id NULL)
build_items(build_id, part_id, position, user_note)

-- Tracking
affiliate_clicks(id, build_id NULL, listing_id, part_id, vendor_id,
                 clicked_at, ip_hash, user_agent)
```

### Key design choices

- **`fitment_rules` is the heart of compatibility.** A part can have multiple rules; lookup returns the highest-priority match per part.
- **Generation > year.** Most car-mod fitment keys on chassis code, not calendar year. We store both, match generation first.
- **Vendor listings separate from parts.** Same Cobb Accessport sold at Summit, ECS, FCP at different prices — the catalog dedupes the part, buy buttons show all listings.
- **Wheel/tire geometry on `parts` and `vehicles` directly.** Geometric fit is computed at query time, not stored as rules.
- **Anonymous builds use a slug** (8-char nanoid), exactly like PCPartPicker.

---

## 4. Scraper Worker

### Module contract

One module per vendor. Each exposes:

```python
@dataclass
class NormalizedPart:
    vendor: str
    vendor_sku: str
    vendor_url: str
    brand: str
    model: str
    name: str
    category_hint: str        # vendor's category string
    image_url: str | None
    price_cents: int | None
    in_stock: bool
    fitment_text: str         # raw vendor fitment prose
    wheel_specs: WheelSpecs | None
    tire_specs: TireSpecs | None

def scrape() -> Iterator[NormalizedPart]: ...
```

### Orchestrator

Runs each vendor module sequentially (parallel for distinct hosts with rate limiting). Three post-processing passes per part:

1. **Category mapping** — vendor strings → our taxonomy. Hand-maintained YAML lookup, fuzzy fallback.
2. **Fitment parsing** — turn `fitment_text` into structured `fitment_rules` rows. Two-pass:
   - Regex first (catches ~80% of standard formats).
   - Haiku LLM fallback for the messy 20%, with strict JSON schema. Cache by `hash(fitment_text)`. Budget ~$5/run.
3. **Deduplication** — collapse duplicates across vendors into one `parts` row with multiple `vendor_listings`. Match on `(brand, model, sku)` first, fuzzy fallback on `(brand, name)`.

### Vendor priority at launch

1. FCP Euro (AvantLink affiliate, Euro platforms) — **Phase 0 first vendor**
2. ECS Tuning (affiliate, Euro platforms)
3. AmericanMuscle (Mustang specialist)
4. RallySport Direct (Subaru/WRX specialist)
5. eBay Motors API (official API, broad fallback inventory)
6. ~~Summit Racing (Impact Radius affiliate, broad tuner coverage)~~ → **DEFERRED to Phase 2**: product detail pages are blocked by Imperva Incapsula and require browser-based scraping (Playwright + stealth) which is out of Phase 0 scope.

### Schedule & legal posture

- Weekly per-vendor cron via GitHub Actions.
- ~1 req/sec rate limit, real `User-Agent`, `From:` email header, respect `robots.txt`.
- Public product pages only. No login walls.
- Upsert behavior: each successful scrape bumps `vendor_listings.last_scraped_at`. Listings missing for 4 consecutive runs are soft-deleted.

### Failure handling

- Sentry alert on > 25% drop in extraction count vs prior run.
- Per-vendor failures isolated — one broken parser doesn't fail the run.
- Old data stays in DB until parser fixed. Catalog can show "last verified N days ago."

---

## 5. Compatibility Engine

### A. "Show me what fits" — catalog query

Conceptually: for each part in the category, find the matching fitment rule with the highest status priority for the user's vehicle, and return that part along with the matching rule's status and caveat. Illustrative shape (real impl uses a window function to break ties on rule priority and avoid duplicate part rows):

```sql
WITH ranked AS (
  SELECT
    p.*,
    fr.status,
    fr.caveat,
    ROW_NUMBER() OVER (
      PARTITION BY p.id
      ORDER BY rule_status_priority(fr.status) DESC
    ) AS rn
  FROM parts p
  JOIN fitment_rules fr ON fr.part_id = p.id
  JOIN vehicles v ON v.id = $vehicle_id
  WHERE p.category_id = $category_id
    AND (fr.make IS NULL OR fr.make = v.make)
    AND (fr.generation IS NULL OR fr.generation = v.generation)
    AND (fr.year_start IS NULL OR v.year >= fr.year_start)
    AND (fr.year_end IS NULL OR v.year <= fr.year_end)
    AND (fr.trims_included IS NULL OR v.trim = ANY(fr.trims_included))
    AND (fr.trims_excluded IS NULL OR v.trim != ALL(fr.trims_excluded))
    AND (fr.body_style IS NULL OR fr.body_style = v.body_style)
)
SELECT * FROM ranked
WHERE rn = 1
ORDER BY rule_status_priority(status) DESC, msrp_cents ASC;
```

Status priority: `fits (3) > fits_with_caveat (2) > unknown (1) > incompatible (0)`. Incompatible parts are returned grayed-out (not filtered) with the reason — users want to know *why* a part doesn't fit them.

### B. Wheel/tire geometric check

Pure function in `lib/wheelfit.ts`. Inputs: wheel `(width, offset)` + vehicle `(stock_offset, max_no_rub_width)`. Outputs:

- `fits` — within stock fender clearance.
- `fits_with_caveat` — pokes ≤ 10mm or needs minor fender rolling.
- `incompatible` — pokes > 25mm or wider than `max_no_rub_width`.

Reference cases lifted from real-world spec sheets used as unit tests.

### C. Cross-part rules in the build

Re-evaluated client-side every time the build changes:

- **Requires:** part's `requires_part_categories` must be satisfied. Example: aftermarket downpipe requires Tune. Missing → yellow warning banner.
- **Conflicts:** part's `conflicts_with_part_ids` must NOT be present. Example: Catback conflicts with Axleback. Both present → red error.

Build state is small (~50 parts max) so these checks are instant client-side. No server round-trip.

---

## 6. Frontend / Build Flow

### Pages

1. **Landing** (`/`) — vehicle selector front and center: cascading dropdowns make → model → year → trim. CTA: "Start building." Below: featured public builds for inspiration.
2. **Build editor** (`/build/[slug]`) — anonymous URL, created on vehicle selection. PCPartPicker-style category rows. Status badges per part. Yellow warning banner sticky at top. "Buy all" footer.
3. **Part picker modal** — opens from each row's "+ Add". Compatible parts at top sorted by price; grayed-out incompatibles below with hover-reason. Filters: brand, price, in-stock-only.
4. **Catalog** (`/parts/[category]`) — browseable index. Each part page (`/part/[brand-slug]/[model-slug]`) statically rendered for SEO.

### UX bets

- **Anonymous-first.** No signup wall. Build URL is the saving mechanism. Optional email capture as a passive prompt after 3+ parts added.
- **Inline warnings, not nags.** One yellow banner at top, badges per row. No popovers, no modals.
- **One-click buy.** Single "Buy" button per row resolves to cheapest in-stock vendor. Power users can expand to see all listings.

---

## 7. Affiliate Redirector

```ts
// app/go/[listing_id]/route.ts
export async function GET(req, { params }) {
  const listing = await db.vendor_listings.findById(params.listing_id);
  if (!listing) return notFound();

  const vendor = await db.vendors.findById(listing.vendor_id);
  const url = new URL(listing.vendor_url);
  url.searchParams.set(vendor.affiliate_param, vendor.affiliate_value);

  await db.affiliate_clicks.insert({
    listing_id: listing.id,
    part_id: listing.part_id,
    vendor_id: vendor.id,
    build_id: req.nextUrl.searchParams.get('build') ?? null,
    ip_hash: hashIP(req.ip),
    user_agent: req.headers.get('user-agent'),
    clicked_at: new Date(),
  });

  return Response.redirect(url.toString(), 302);
}
```

Click logging awaited but failure-tolerant. IP hashed for analytics, not stored raw.

---

## 8. Phasing

**Phase 0 — Foundation (weeks 1-3)**
- DB schema + migrations.
- `vehicles` seed (~12 chassis × ~5 years × ~3 trims ≈ 180 rows, hand-entered).
- One scraper end-to-end (FCP Euro; Summit Racing deferred to Phase 2 — see §4).
- Read-only catalog page rendering scraped data.

**Phase 1 — MVP (weeks 4-8)**
- Build editor with category rows, compatibility engine, anonymous slugs.
- Wheel/tire geometric fit calculator with unit tests.
- Affiliate redirector with click logging.
- Two more scrapers (FCP Euro + AmericanMuscle).
- Landing page + part detail pages (SEO).

**Phase 2 — Polish (weeks 9-12)**
- 3 more scrapers (ECS Tuning, RallySport Direct, eBay Motors API).
- Optional accounts (email magic link, save builds, "my garage").
- Public build pages + "fork this build."
- Better fitment quality: regex pass + Haiku LLM fallback wired in.
- Sentry, basic analytics dashboard.

**Future (no MVP commitment):** 3D render (or 2D layered alternative), exhaust sound preview, community fitment notes, mobile app, build sharing/social.

---

## 9. Error Handling

Three failure modes worth designing for; the rest are normal-app concerns.

1. **Scraper breaks (vendor changes HTML).** Parser returns near-zero parts → Sentry alert ("extracted < 50% of last successful run"). Old data stays in DB until parser fixed. Catalog shows "last verified N days ago" if stale.
2. **Fitment ambiguity.** Vendor lists "Fits 2015+ WRX" with no end year. Parser writes `year_end = NULL`. Mitigation: if a vehicle's year is more than 3 years past the rule's most recent confirmed match, downgrade `status` from `fits` to `unknown`.
3. **Vendor link rot.** A `vendor_url` 404s → flagged `in_stock = false` on next scrape. Affiliate redirector still works (vendor's own UX problem). After 4 consecutive missing scrapes, soft-delete the listing.

User-facing surfaces: warning banner at top of build, status badges per part, hover-reason for grayed-out incompatibles. App-level errors fall back to standard error page.

---

## 10. Testing Strategy

- **Compatibility engine** — unit tests with hand-built fitment scenarios. One "golden" test per platform: real-world build sourced from forum threads, asserts engine produces correct warnings/conflicts. Highest-value test surface.
- **Wheel/tire fit math** — pure-function unit tests with reference cases from real spec sheets (e.g. "18×9.5 +35 on a 2018 WRX = pokes 8mm = `fits_with_caveat`").
- **Fitment text parser** — snapshot tests on ~50 example strings per vendor. Add a snapshot whenever a parser fails on a real string.
- **Scraper modules** — integration tests against recorded HTML fixtures (not live sites). Re-record fixtures monthly.
- **End-to-end** — Playwright on staging: pick vehicle → add 5 parts → see expected warnings → click affiliate → assert redirect with affiliate code in URL.

Skip: trivial CRUD unit tests, snapshot tests on UI components, coverage targets.

---

## 11. Open questions / things to decide later

These don't block implementation start but should be answered before launch:

1. **Brand name.** "CarPartPicker" is a placeholder; legal/SEO check before going public.
2. **Affiliate program signups.** Apply to Impact Radius (Summit), AvantLink (FCP), and AmericanMuscle's program before launch. Some have approval delays.
3. **Hosting cost ceiling.** Confirm Neon free tier handles expected query load; budget for ~$25/mo across Vercel + Neon + Sentry.
4. **Vehicle seed data source.** Hand-enter 120 rows or scrape Edmunds / NHTSA VIN database. Hand-entry probably faster for MVP.
5. **Brand normalization.** Same brand spelled differently across vendors ("COBB" vs "Cobb Tuning" vs "Cobb"). Manual mapping table at launch, possibly LLM-assisted later.

---

## 12. Decisions log (for future-Teo)

- **3D render deferred to future**, not Phase 2. Cost too high for current team. If revisited, start with 2D layered overlays before full 3D.
- **Tier 3 mod scope on 8 narrow platforms** rather than Tier 1 on every car. Niche-deep beats wide-shallow for MVP traction.
- **Hybrid data strategy (D)** — scrape backbone now, community notes layered later. MVP is scrape-only; community features only after user base exists.
- **GitHub Actions over Fly.io** for the scraper. Free, version-controlled cron.
- **Anonymous builds with slug URL** rather than required accounts. Lowest friction; matches PCPartPicker.
- **Affiliate buy-through** as monetization. No cart aggregation (too operational for MVP).
- **Incompatibles shown grayed-out**, not hidden. Users want to know *why* a part doesn't fit.
