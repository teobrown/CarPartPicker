# Re-categorize the parts catalog

**Date:** 2026-05-03
**Owner:** Teo
**Status:** Approved, ready for implementation plan

---

## Problem

The catalog's 18 flat categories blur distinct product types. Symptoms a user surfaced:

- The `intake` bucket holds cold-air intakes, short-rams, ram-airs, intake manifolds, MAF housings, intake hoses, air filters, and turbo inlet pipes — all in one row of the build editor.
- The `catback` bucket holds catbacks, front-pipes (mid-pipe), downpipes, downpipe gaskets, exhaust adapters, and exhaust+intake bundles.
- The `coilovers` bucket holds Audi/VW control-arm kits.
- The `wheels` bucket holds lug nuts, wheel studs, valve caps, centering rings, and center caps alongside actual wheels.
- The `tune` bucket holds 1 part total. Several taxonomies (e.g., brakes) are absent entirely.

These two failure modes are independent. Coarse buckets (B) leave shoppers digging through irrelevant parts; mis-categorization (A) puts wrong parts in even the right bucket. The fix is both: a new fine-grained taxonomy AND a re-classification of the 1841 existing parts.

## Design

### 1. Taxonomy — two-level, parent groups + leaves

10 parent groups, 33 user-facing leaves, plus one admin-only `misc` leaf under an `internal` parent.

```
Intake (parent)
  cold-air-intake, short-ram-intake, ram-air-intake,
  intake-manifold, air-filter, intake-hose, maf-housing
Exhaust (parent)
  catback-exhaust, axleback-exhaust, front-pipe, downpipe,
  muffler-delete, exhaust-tip, o2-sensor, exhaust-hardware
Forced Induction (parent)
  intercooler, charge-pipe, bov, wastegate
Tuning (parent)
  ecu-tune, wideband-gauge
Suspension (parent)
  coilovers, lowering-springs, sway-bars, end-links,
  control-arms, strut-bar, camber-kit, bushings
Wheels & Tires (parent)
  wheels, tires, wheel-spacers, lug-nuts-studs, hub-rings
Brakes (parent)
  brake-pads, brake-rotors, brake-lines, big-brake-kit
Body & Aero (parent)
  front-lip, side-skirts, rear-diffuser, spoiler-wing, hood, fender-flares
Lighting (parent)
  headlights, taillights, fog-lights, led-bulbs
Internal (parent, admin-only)
  misc       ← hidden_from_picker = true
```

Slug uniqueness across the whole table is preserved: parent slugs (`intake`, `exhaust`, `suspension`, etc.) reuse the same names the old leaves used, but the old leaves are renamed (`intake` → repurposed as parent; old `catback` → renamed to `catback-exhaust` leaf).

### 2. Schema changes

`categories` already has `parent_id` (unused). One column added:

```ts
hiddenFromPicker: boolean('hidden_from_picker').default(false).notNull()
```

The picker (`/api/builds/[slug]/items` add-flow) and the catalog browse pages filter `hiddenFromPicker = false`. Direct URL `/parts/misc` still works for admin review. No other schema changes.

### 3. Re-classification — heuristic + LLM fallback

A new one-shot script `scraper/src/scraper/reclassify.py` walks every part and computes a new `category_id` in two stages:

**Stage A — heuristic.** ~40 keyword/regex rules over `parts.name` + `parts.brand`. Examples:

- `cold[ -]?air` → `cold-air-intake`
- `short[ -]?ram` → `short-ram-intake`
- `ram[ -]?air` → `ram-air-intake`
- `intake manifold` → `intake-manifold`
- `(front[- ]?pipe|j[- ]?pipe|over[- ]?pipe|mid[- ]?pipe)` → `front-pipe`
- `(o2 sensor|oxygen sensor|wideband o2)` → `o2-sensor`
- `(lug nut|wheel stud|valve cap|valve stem|center cap|centering ring)` → `lug-nuts-studs`
- `control arm` → `control-arms`
- `(end link|sway end link)` → `end-links`
- `strut bar|chassis brace` → `strut-bar`
- `camber arm|camber kit|camber bolt` → `camber-kit`
- `(bushing|subframe bushing)` → `bushings`
- `wheel spacer|hub spacer` → `wheel-spacers`
- `(brake pad|caliper pad)` → `brake-pads`
- `brake rotor|brake disc` → `brake-rotors`
- `brake line|stainless line` → `brake-lines`
- `big brake|caliper kit|bbk` → `big-brake-kit`
- `charge pipe|hot pipe|boost pipe` → `charge-pipe`
- `wastegate` → `wastegate`
- `(diverter valve|blow off|bov|bpv)` → `bov`
- `wideband|af gauge|boost gauge` → `wideband-gauge`
- `headlight|head lamp` → `headlights`
- `taillight|tail lamp` → `taillights`
- `fog light|fog lamp` → `fog-lights`
- `led bulb|h11|9005|9006|hid kit` → `led-bulbs`
- `(splitter|front lip)` → `front-lip`
- `side skirt` → `side-skirts`
- `rear diffuser|underbody diffuser` → `rear-diffuser`
- `(spoiler|wing|ducktail)` → `spoiler-wing`
- `(hood|bonnet)` → `hood`
- `fender flare` → `fender-flares`
- `(catback|cat-back|cat back)` → `catback-exhaust`
- `(axleback|axle-back|axle back)` → `axleback-exhaust`
- `downpipe|down pipe|j-pipe lower` → `downpipe`
- `muffler delete` → `muffler-delete`
- `exhaust tip|tail pipe tip` → `exhaust-tip`
- `(intake hose|silicone hose|silicone intake)` → `intake-hose`
- `maf housing` → `maf-housing`
- `air filter|panel filter|drop[ -]?in filter` → `air-filter`
- `intercooler` → `intercooler`
- `(coilover|height adjustable suspension)` → `coilovers`
- `(lowering spring|sport spring|drop spring)` → `lowering-springs`
- `(sway bar|anti[ -]?roll bar)` → `sway-bars`
- `wheel\b` (as fallback after wheel-hardware rules) → `wheels`
- `tire\b` → `tires`

The current `category_id` is consulted as a *prior* — heuristic rules can use it to disambiguate. E.g., a part named "C&L CX2 Rear Shock" currently in `coilovers` → coilovers; same name currently in `springs` → lowering-springs.

**Stage B — LLM fallback.** Parts the heuristic can't classify go through DeepSeek (`scraper/src/scraper/llm_fitment.py` already has the client + caching). Prompt: "Given this product name + brand + description, return one slug from this list: …". Cached by sha256 of input.

**Stage C — misc.** Anything Stage B also can't place gets `category_id = misc`. Hidden from picker. Reviewable via `/parts/misc`.

Stages A → B → C are sequential; first hit wins. The script is idempotent — re-running on a fully re-classified DB is a no-op (every part already has a non-old `category_id`).

### 4. Migration sequence

One Drizzle migration `0006_recategorize.sql` and one Python re-classify run.

1. SQL: `ALTER TABLE categories ADD COLUMN hidden_from_picker boolean NOT NULL DEFAULT false`.
2. SQL: suffix every existing category slug with `-old` so none collide with new parent or leaf slugs (`UPDATE categories SET slug = slug || '-old'`). Old rows stay alive (parts still reference their `id`) until step 6 deletes them.
3. SQL: insert all 10 parent rows (`intake`, `exhaust`, `forced-induction`, `tuning`, `suspension`, `wheels-tires`, `brakes`, `body-aero`, `lighting`, `internal`) with `parent_id = NULL`.
4. SQL: insert all 34 leaf rows (33 visible + 1 misc) with correct `parent_id`; `misc` gets `hidden_from_picker = true`.
5. Python: `uv run python -m scraper.reclassify`. Walks `parts`, classifies via heuristic → LLM → misc, updates `parts.category_id` to a new leaf id. Logs counts (`heuristic=N llm=N misc=N`). Idempotent.
6. SQL: `DELETE FROM categories WHERE slug LIKE '%-old'`. Every old row's parts have moved to a new leaf (or to misc) so this is safe; FK references go to zero.

### 5. Downstream changes

- **Scraper category map** — `scraper/category_map.yaml` rewritten to point each vendor-category string at the correct fine-grained leaf. Future scrapes upsert directly into the right leaf, bypassing re-classification.
- **Scraper slug overrides** — values in `orchestrator.py` that currently anchor a vendor seed URL to a coarse slug (e.g. AmericanMuscle's `aftermarket-performance-exhaust.html` → `catback`) become *hints* only. The post-upsert re-classifier still runs and can override.
- **Tests** — `tests/unit/compat.test.ts` references slugs `intake` and `catback` in fixtures; rename to `cold-air-intake` and `catback-exhaust`.
- **UI / build editor** — currently shows ~18 flat category rows. With ~33 visible leaves, switch to a **parent-grouped accordion**: parent header collapsible, leaf rows underneath. Defer this UI work to a follow-up commit so the data migration ships first; the existing flat rendering still works (just longer).
- **Catalog index** — `app/parts/page.tsx` should group categories by parent for display. Same template as build editor accordion. Same defer policy.

## Out of scope (this phase)

- Brake pads/rotors/lines, hood, splitter, side skirts, etc. have **no parts in the catalog yet**. The schema row exists; populating them is a future scraper / vendor task.
- `turbocharger`, `supercharger`, standalone ECU, clutch, flywheel, short shifter — not in catalog, not added to taxonomy (high-cost, low-traffic items).
- Old URL redirects (`/parts/intake` → 404 vs 301 to `/parts/cold-air-intake`). Domain has zero traffic; accept 404 for now.

## Risks

- **LLM cost at scale** — 1841 parts × ~500 tokens each at DeepSeek prices ≈ $0.10. Acceptable.
- **Heuristic over-classification** — a regex rule might pull a part into the wrong leaf (e.g., an exhaust gasket caught by `exhaust` rule when `o2-sensor` was the right answer). Mitigation: rules ordered most-specific first; `exhaust-hardware` is the catch-all for unmatched exhaust-related strings.
- **Vendor mis-mappings persist** — if `category_map.yaml` is wrong post-migration, future scrapes re-introduce mis-categorization. Mitigation: re-classifier can be re-run after each scrape (idempotent), at the cost of one DeepSeek pass.

