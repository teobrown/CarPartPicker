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
 * Vendor product names rarely say "Volkswagen Golf R Mk7" verbatim — they say "VW", "MQB", "MK7",
 * "Golf", "GTI", etc. This map covers the 8 platform groups in our seed.
 */
const MAKE_SYNONYMS: Record<string, string[]> = {
  Subaru:     ['subaru', 'wrx', 'sti', 'brz', 'impreza', 'forester', 'va chassis', 'vb chassis'],
  Toyota:     ['toyota', 'gr86', 'gr 86', 'gr corolla', 'corolla', 'zn8'],
  Honda:      ['honda', 'civic', 'type r', 'fk8', 'fl5', 'fe1'],
  Ford:       ['ford', 'mustang', 's550', 'ecoboost', 'gt'],
  Mazda:      ['mazda', 'mx-5', 'mx 5', 'miata', 'nd'],
  Volkswagen: ['volkswagen', 'vw', 'golf', 'gti', 'mqb', 'mk7', 'mk8', 'ea888'],
};

function partLooksRelevantToMake(partName: string, partBrand: string, vehicleMake: string): boolean {
  const synonyms = MAKE_SYNONYMS[vehicleMake] ?? [vehicleMake.toLowerCase()];
  const haystack = `${partName} ${partBrand}`.toLowerCase();
  return synonyms.some((s) => haystack.includes(s));
}

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

  function ruleMatches(r: (typeof rules)[number]): boolean {
    if (r.make != null && r.make !== v.make) return false;
    if (r.model != null && r.model !== v.model) return false;
    if (r.generation != null && r.generation !== v.generation) return false;
    if (r.yearStart != null && v.year < r.yearStart) return false;
    if (r.yearEnd != null && v.year > r.yearEnd) return false;
    if (r.bodyStyle != null && r.bodyStyle !== v.bodyStyle) return false;
    if (
      r.trimsIncluded &&
      r.trimsIncluded.length > 0 &&
      (!v.trim || !r.trimsIncluded.includes(v.trim))
    )
      return false;
    if (
      r.trimsExcluded &&
      r.trimsExcluded.length > 0 &&
      v.trim &&
      r.trimsExcluded.includes(v.trim)
    )
      return false;
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
    .map((r) => {
      const rule = byPart[r.id];
      if (rule) return { ...r, status: rule.status, caveat: rule.caveat };
      // No matching fitment rule. With a vehicle selected, fall back to a name heuristic:
      // if the part name/brand mentions the vehicle's make (or known synonyms), keep "unknown"
      // (we don't *know* it fits, but it's plausible). Otherwise demote to "incompatible".
      const looksRelevant = partLooksRelevantToMake(r.name, r.brand, v.make);
      return {
        ...r,
        status: looksRelevant ? ('unknown' as CompatStatus) : ('incompatible' as CompatStatus),
        caveat: looksRelevant ? null : `No fitment match for ${v.make}`,
      };
    })
    .sort((a, b) => STATUS_PRIORITY[b.status] - STATUS_PRIORITY[a.status]);
}
