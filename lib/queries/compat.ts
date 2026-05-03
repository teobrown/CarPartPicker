/**
 * v1 compat engine.
 *
 * Status priority: fits (3) > fits_with_caveat (2) > unknown (1) > incompatible (0).
 *
 * When a part has at least one matching fitment_rules row for the selected vehicle,
 * the highest-priority rule's status is used. When NO rule matches, we fall back to
 * a make-name heuristic on the part's text — see partLooksRelevantToMake. This is a
 * Phase 1 stopgap; the proper fix is a Haiku-LLM fallback in the fitment parser
 * (spec §4, Phase 2) that produces structured fitment_rules from prose descriptions
 * like FCP Euro's JSON-LD `description` field.
 */
import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, fitmentRules, vehicles } from '@/lib/db/schema';
import { sql, eq, and, inArray, min } from 'drizzle-orm';

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

/**
 * Make-level synonyms — last-resort fallback when no model-level entry exists.
 * Avoid platform-confusing terms here (e.g. NO 'civic' on Honda — Civic Si and
 * Civic Type R are separate vehicles and need their own model-level rules).
 */
const MAKE_SYNONYMS: Record<string, string[]> = {
  Subaru:     ['subaru', 'impreza', 'va chassis', 'vb chassis'],
  Toyota:     ['toyota'],
  Honda:      ['honda'],
  Ford:       ['ford'],
  Mazda:      ['mazda'],
  Volkswagen: ['volkswagen', 'vw', 'mqb', 'ea888'],
};

/**
 * Model-level synonyms with positive (`yes`) and negative (`no`) lists.
 * Keyed by `vehicle.model` (or `vehicle.model + ' ' + vehicle.subModel` for
 * Mustang variants) — see `vehicleMatchKey()` below.
 *
 * The `no` list is critical: it prevents Civic Type R parts from matching
 * Civic Si vehicles, GTI parts from matching Golf R, axleback parts from
 * matching catbacks, etc. Stops the heuristic from over-matching.
 */
const MODEL_SYNONYMS: Record<string, { yes: string[]; no: string[] }> = {
  // Subaru
  WRX:               { yes: ['wrx'],                                    no: ['sti'] },
  'WRX STI':         { yes: ['sti', 'wrx sti', 'wrx-sti'],              no: [] },
  BRZ:               { yes: ['brz', 'zd8'],                             no: ['gr86', 'gr 86', 'frs', 'fr-s'] },
  // Toyota
  'GR Corolla':      { yes: ['gr corolla', 'gr-corolla'],               no: ['gr86', 'gr 86'] },
  GR86:              { yes: ['gr86', 'gr 86', 'zn8', 'frs', 'fr-s'],    no: ['brz', 'gr corolla'] },
  // Honda
  'Civic Si':        { yes: ['civic si', 'civic-si', 'fe1', 'si sedan'], no: ['type r', 'type-r', 'typer', 'fk8', 'fl5'] },
  'Civic Type R':    { yes: ['type r', 'type-r', 'typer', 'fk8', 'fl5'], no: ['civic si', ' si '] },
  // Ford — Mustang split via subModel
  'Mustang GT':      { yes: ['mustang gt', '5.0l mustang', 'mustang 5.0', 'gt mustang'], no: ['ecoboost', '2.3l', 'shelby'] },
  'Mustang Ecoboost':{ yes: ['ecoboost', '2.3l mustang', 'mustang ecoboost'],            no: ['mustang gt', '5.0l', 'mustang 5.0', 'shelby'] },
  // Mazda
  'MX-5 Miata':      { yes: ['mx-5', 'mx 5', 'miata'],                  no: [] },
  // Volkswagen
  'Golf R':          { yes: ['golf r', 'golf-r', 'mk7 r', 'mk8 r'],     no: ['gti'] },
  GTI:               { yes: ['gti'],                                    no: ['golf r', 'golf-r'] },
};

/** Build the key into MODEL_SYNONYMS for a given vehicle. */
function vehicleMatchKey(vehicle: { model: string; subModel: string | null }): string {
  // Mustang rows have model='Mustang' + subModel='GT' or 'Ecoboost'.
  if (vehicle.model === 'Mustang' && vehicle.subModel) {
    return `${vehicle.model} ${vehicle.subModel}`;
  }
  return vehicle.model;
}

/**
 * Heuristic: does the part name/brand text plausibly mention this vehicle's
 * specific model (with sub-model awareness for Mustang)?
 *
 * Returns true (plausible) if any positive synonym is in the haystack AND no
 * negative synonym is in the haystack. Falls back to make-level check if the
 * model isn't in MODEL_SYNONYMS.
 *
 * Used only when no fitment_rule explicitly matches the vehicle.
 */
function partLooksRelevantToVehicle(
  partName: string,
  partBrand: string,
  vehicle: { make: string; model: string; subModel: string | null },
): boolean {
  // Pad with spaces so single-letter "no" tokens like " si " match word boundaries.
  const haystack = ` ${partName} ${partBrand} `.toLowerCase();
  const key = vehicleMatchKey(vehicle);
  const modelRules = MODEL_SYNONYMS[key];
  if (modelRules) {
    if (modelRules.no.some((s) => haystack.includes(s))) return false;
    if (modelRules.yes.some((s) => haystack.includes(s))) return true;
    // Model defined but no positive match — fall through to make check.
  }
  const makeSynonyms = MAKE_SYNONYMS[vehicle.make] ?? [vehicle.make.toLowerCase()];
  return makeSynonyms.some((s) => haystack.includes(s));
}

/**
 * Strong-NO signal: part name explicitly mentions a sub-model that is not
 * this vehicle's. e.g., "Mustang GT" in name when vehicle is Ecoboost, or
 * "Type R" when vehicle is Civic Si. Used to override an LLM "fits" verdict
 * — the synonym lists are hardcoded and reliable, the rule isn't.
 *
 * Multi-platform parts whose names list both sub-models in an OR style
 * (e.g. "Steeda Springs (S550 Mustang GT/V6/EcoBoost)") will hit BOTH a
 * positive AND a negative synonym. In that case we trust the rule and do
 * not demote — only an unambiguous opposite-only mention triggers conflict.
 */
function partHasModelConflict(
  partName: string,
  partBrand: string,
  vehicle: { make: string; model: string; subModel: string | null },
): boolean {
  const haystack = ` ${partName} ${partBrand} `.toLowerCase();
  const key = vehicleMatchKey(vehicle);
  const modelRules = MODEL_SYNONYMS[key];
  if (!modelRules) return false;
  const hasNegative = modelRules.no.some((s) => haystack.includes(s));
  if (!hasNegative) return false;
  const hasPositive = modelRules.yes.some((s) => haystack.includes(s));
  return !hasPositive;
}

/**
 * Canonical trim/sub-model token whitelist. Used to (a) decide whether
 * `trimsIncluded` is real signal vs LLM-extraction noise (year ranges,
 * CSS, body styles dumped into the field), and (b) sanitize caveat
 * strings so users don't see "requires Department of Transportation
 * trim". Match is case-insensitive and whole-string anchored.
 *
 * Update when seed adds new trims/sub-models. See `lib/db/seed/vehicles.ts`.
 */
const REAL_TRIM_PATTERN =
  /^(base|premium|limited|sport[- ]?tech|core|circuit|morizo|gt|eco[- ]?boost|gt350|gt500|mach 1|cobra|performance pack|high performance|sport|club|touring|grand touring|rf|dcc|si|type[- ]?r|rs|sti|gti|golf r|dark horse|autobahn|s|se)$/i;

function isRealTrim(t: string | null | undefined): boolean {
  return REAL_TRIM_PATTERN.test((t ?? '').trim());
}

/**
 * Rank parts in a category by compatibility for a given vehicle. If vehicleId is null,
 * everything is "unknown".
 *
 * `hideIncompatible: true` drops parts that look clearly wrong for the selected
 * vehicle (different make, no name overlap). The build-editor part picker uses this:
 * users only want to see parts that could plausibly fit. Catalog browse pages don't
 * pass it, so they keep showing incompatibles grayed-out — those pages exist for
 * "what does this part fit" exploration, not buying.
 *
 * `hideIncompatible` is a no-op when vehicleId is null (no vehicle = no signal to
 * filter on).
 */
export async function listCategoryPartsRankedForVehicle(opts: {
  categorySlug: string;
  vehicleId: number | null;
  search?: string;
  hideIncompatible?: boolean;
}): Promise<RankedPartRow[]> {
  const { categorySlug, vehicleId, search, hideIncompatible = false } = opts;

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
        search
          ? sql`(${parts.brand} ILIKE ${'%' + search + '%'} OR ${parts.model} ILIKE ${'%' + search + '%'} OR ${parts.name} ILIKE ${'%' + search + '%'})`
          : sql`true`,
      ),
    )
    .groupBy(parts.id);

  // Fast path: nothing in the category (or matching the search) — return empty
  // before we do an `IN ()` query that Postgres can't parse.
  if (baseRows.length === 0) return [];

  if (vehicleId == null) {
    return baseRows.map((r) => ({ ...r, status: 'unknown' as const, caveat: null }));
  }

  // Step 2: get the vehicle row to drive matching
  const [v] = await db.select().from(vehicles).where(eq(vehicles.id, vehicleId)).limit(1);
  if (!v) {
    return baseRows.map((r) => ({ ...r, status: 'unknown' as const, caveat: null }));
  }

  // Step 3: for each part, find matching fitment rules and pick the highest-priority status
  const partIds = baseRows.map((r) => r.id);
  const rules = await db
    .select()
    .from(fitmentRules)
    .where(inArray(fitmentRules.partId, partIds));

  // LLM extraction often dumps non-trim noise into trims_included (year ranges,
  // body-style fragments, exclusion phrases, even CSS). We enforce the trim
  // filter ONLY when the list contains at least one entry that matches our
  // canonical trim/sub-model pattern — otherwise the list is treated as
  // informational and skipped. The model-aware name heuristic (applied later
  // as a sanity check on rule "fits" verdicts) handles sub-model
  // differentiation when the trim filter is bypassed this way.
  function trimMatches(r: (typeof rules)[number]): boolean {
    if (!r.trimsIncluded || r.trimsIncluded.length === 0) return true;
    const realTrims = r.trimsIncluded.filter(isRealTrim);
    if (realTrims.length === 0) return true; // all garbage, skip filter
    const matchTrim = v.trim != null && realTrims.some((t) => t.toLowerCase() === v.trim!.toLowerCase());
    const matchSub = v.subModel != null && realTrims.some((t) => t.toLowerCase() === v.subModel!.toLowerCase());
    return matchTrim || matchSub;
  }

  function ruleMatches(r: (typeof rules)[number]): boolean {
    if (r.make != null && r.make !== v.make) return false;
    if (r.model != null && r.model !== v.model) return false;
    if (r.generation != null && r.generation !== v.generation) return false;
    if (r.yearStart != null && v.year < r.yearStart) return false;
    if (r.yearEnd != null && v.year > r.yearEnd) return false;
    if (r.bodyStyle != null && r.bodyStyle !== v.bodyStyle) return false;
    if (!trimMatches(r)) return false;
    if (
      r.trimsExcluded &&
      r.trimsExcluded.length > 0 &&
      v.trim &&
      r.trimsExcluded.includes(v.trim)
    )
      return false;
    return true;
  }

  // True when this rule explicitly names the vehicle's model (with optional
  // matching make). Used to detect "the LLM/vendor told us about this part
  // for THIS model — just for different years/trims/etc." When that's true
  // and `ruleMatches` returns false, the part is genuinely incompatible:
  // the rule is authoritative on year/trim bounds and must outrank the
  // heuristic. We require r.model non-null so a generic "fits some Ford"
  // rule (model=null) doesn't lock all out-of-range Ford parts to
  // incompatible — those fall through to the heuristic instead.
  function ruleClaimsModel(r: (typeof rules)[number]): boolean {
    if (r.model == null) return false;
    if (r.model !== v.model) return false;
    if (r.make != null && r.make !== v.make) return false;
    return true;
  }

  function explainModelMissed(rs: (typeof rules)[number][]): string | null {
    const ranges = new Set<string>();
    const trims = new Set<string>();
    for (const r of rs) {
      if (r.yearStart != null || r.yearEnd != null) {
        const a = r.yearStart != null ? String(r.yearStart) : '';
        const b = r.yearEnd != null ? String(r.yearEnd) : 'newer';
        ranges.add(a && b ? `${a}-${b}` : a || b);
      }
      // Filter trim noise — only surface canonical trims so the user-facing
      // caveat doesn't say "requires Department of Transportation trim".
      if (r.trimsIncluded) {
        for (const t of r.trimsIncluded) {
          if (isRealTrim(t)) trims.add(t);
        }
      }
    }
    const vehicleLabel = v.subModel
      ? `${v.year} ${v.make} ${v.model} ${v.subModel}`
      : `${v.year} ${v.make} ${v.model}`;
    const parts: string[] = [];
    if (ranges.size) parts.push(`Fits ${[...ranges].join(', ')}`);
    if (trims.size) parts.push(`requires ${[...trims].join('/')} trim`);
    if (!parts.length) return `Doesn't fit ${vehicleLabel}`;
    return `${parts.join('; ')} — not ${vehicleLabel}`;
  }

  // Group rules by part. Decision per part is staged:
  //   1. any rule matches → use highest-priority status,
  //   2. else any rule names this make+model but missed (year/trim/etc) → incompatible,
  //   3. else fall through to the model-name heuristic.
  // A rule "fits" verdict is then sanity-checked against the model-aware name
  // heuristic so LLM rule errors around sub-model differentiation can't make a
  // GT-only part show as fits for an Ecoboost (or vice versa).
  const rulesByPart = new Map<number, (typeof rules)[number][]>();
  for (const r of rules) {
    const list = rulesByPart.get(r.partId) ?? [];
    list.push(r);
    rulesByPart.set(r.partId, list);
  }

  const vehicleLabel = v.subModel ? `${v.make} ${v.model} ${v.subModel}` : `${v.make} ${v.model}`;

  const ranked = baseRows
    .map((r) => {
      const partRules = rulesByPart.get(r.id) ?? [];
      const heuristicSaysRelevant = partLooksRelevantToVehicle(r.name, r.brand, v);

      // Stage 1: best matching rule.
      let best: { status: CompatStatus; caveat: string | null } | null = null;
      for (const rule of partRules) {
        if (!ruleMatches(rule)) continue;
        const status = (rule.status as CompatStatus) ?? 'unknown';
        if (!best || STATUS_PRIORITY[status] > STATUS_PRIORITY[best.status]) {
          best = { status, caveat: rule.caveat };
        }
      }
      if (best) {
        // Sanity-check positive verdicts against the model-conflict heuristic.
        // If the part name explicitly names a different sub-model (e.g.,
        // "Mustang GT" in name but vehicle is Ecoboost), demote — the LLM
        // rule is unreliable on sub-model boundaries, the synonym lists are
        // hardcoded. Absence of a positive name match is NOT a demotion
        // signal (Cobb SF Intake fits a WRX even if "WRX" isn't in the name).
        if (
          (best.status === 'fits' || best.status === 'fits_with_caveat') &&
          partHasModelConflict(r.name, r.brand, v)
        ) {
          return {
            ...r,
            status: 'incompatible' as CompatStatus,
            caveat: `Part name doesn't match ${vehicleLabel}`,
          };
        }
        return { ...r, status: best.status, caveat: best.caveat };
      }

      // Stage 2: rule explicitly names this make+model but didn't match → incompatible.
      const modelClaims = partRules.filter(ruleClaimsModel);
      if (modelClaims.length > 0) {
        return {
          ...r,
          status: 'incompatible' as CompatStatus,
          caveat: explainModelMissed(modelClaims),
        };
      }

      // Stage 3: pure model-aware name heuristic.
      return {
        ...r,
        status: heuristicSaysRelevant ? ('unknown' as CompatStatus) : ('incompatible' as CompatStatus),
        caveat: heuristicSaysRelevant ? null : `No fitment match for ${vehicleLabel}`,
      };
    })
    .sort((a, b) => STATUS_PRIORITY[b.status] - STATUS_PRIORITY[a.status]);

  if (hideIncompatible) {
    return ranked.filter((r) => r.status !== 'incompatible');
  }
  return ranked;
}
