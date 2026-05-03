import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, vendors, vehicles } from '@/lib/db/schema';
import { sql, eq, min, count, countDistinct, and, isNotNull } from 'drizzle-orm';

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
    // Match the SQL-side slugify to lib/format.ts#partSlug exactly:
    //   lowercase → collapse runs of any non-alphanumeric char to '-' → trim '-' from ends.
    // Without this regex pair, brands like "K&N" and models containing parens / slashes
    // produced UI slugs that wouldn't match the SQL `replace(_, ' ', '-')` shortcut → 404.
    .where(sql`trim(BOTH '-' FROM regexp_replace(lower(${parts.brand}), '[^a-z0-9]+', '-', 'g')) = ${brandSlug}
           AND trim(BOTH '-' FROM regexp_replace(lower(${parts.model}), '[^a-z0-9]+', '-', 'g')) = ${modelSlug}`)
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

export type CatalogStats = {
  vehicleCount: number;
  partCount: number;
  listingCount: number;
  vendorCount: number;
  categoryCount: number;
  platformGroups: number;
};

export async function getCatalogStats(): Promise<CatalogStats> {
  const [v] = await db.select({ n: count() }).from(vehicles);
  const [p] = await db.select({ n: count() }).from(parts);
  const [l] = await db.select({ n: count() }).from(vendorListings);
  const [vd] = await db.select({ n: count() }).from(vendors);
  // categoryCount surfaces in the homepage stats band as "Categories" — the
  // user-facing number, so count only picker-visible leaves (no parent groups,
  // no admin-only `misc`).
  const [c] = await db
    .select({ n: count() })
    .from(categories)
    .where(and(isNotNull(categories.parentId), eq(categories.hiddenFromPicker, false)));
  const [pg] = await db
    .select({ n: countDistinct(vehicles.model) })
    .from(vehicles);
  return {
    vehicleCount: v.n,
    partCount: p.n,
    listingCount: l.n,
    vendorCount: vd.n,
    categoryCount: c.n,
    platformGroups: pg.n,
  };
}

export type PlatformSummary = {
  make: string;
  model: string;
  generation: string;
  yearStart: number;
  yearEnd: number;
  rowCount: number;
};

export async function listPlatforms(): Promise<PlatformSummary[]> {
  const rows = await db
    .select({
      make: vehicles.make,
      model: vehicles.model,
      generation: vehicles.generation,
      yearStart: sql<number>`min(${vehicles.year})::int`,
      yearEnd: sql<number>`max(${vehicles.year})::int`,
      rowCount: sql<number>`count(*)::int`,
    })
    .from(vehicles)
    .groupBy(vehicles.make, vehicles.model, vehicles.generation)
    .orderBy(vehicles.make, vehicles.model, vehicles.generation);
  return rows;
}

export type CategorySummary = {
  slug: string;
  name: string;
  partCount: number;
};

export type CategoryGroup = {
  parentSlug: string;
  parentName: string;
  totalParts: number;
  leaves: CategorySummary[];
};

/**
 * Picker-visible leaves grouped under their parent. Used by the catalog
 * index, the homepage category band, and the build-editor add-part menu.
 * Parents and `misc` are excluded — same filter as `listCategoriesWithCounts`,
 * just shaped so consumers can render parent headers + child links instead
 * of a flat 48-row list.
 *
 * Single round-trip via a self-join. Output is ordered by parent.id then
 * leaf.id (display order matches the seed).
 */
export async function listCategoriesGrouped(): Promise<CategoryGroup[]> {
  const rows = await db.execute<{
    parent_slug: string;
    parent_name: string;
    leaf_slug: string;
    leaf_name: string;
    part_count: number;
  }>(sql`
    SELECT
      parent.slug AS parent_slug,
      parent.name AS parent_name,
      leaf.slug   AS leaf_slug,
      leaf.name   AS leaf_name,
      COUNT(p.id)::int AS part_count
    FROM categories leaf
    JOIN categories parent ON parent.id = leaf.parent_id
    LEFT JOIN parts p ON p.category_id = leaf.id
    WHERE leaf.hidden_from_picker = false
      AND parent.hidden_from_picker = false
    GROUP BY parent.id, parent.slug, parent.name, leaf.id, leaf.slug, leaf.name
    ORDER BY parent.id, leaf.id
  `);

  const groups: CategoryGroup[] = [];
  let cur: CategoryGroup | null = null;
  for (const r of rows) {
    if (cur === null || cur.parentSlug !== r.parent_slug) {
      cur = {
        parentSlug: r.parent_slug,
        parentName: r.parent_name,
        totalParts: 0,
        leaves: [],
      };
      groups.push(cur);
    }
    cur.leaves.push({ slug: r.leaf_slug, name: r.leaf_name, partCount: r.part_count });
    cur.totalParts += r.part_count;
  }
  return groups;
}

/**
 * Picker-visible leaves only: rows that are children of a parent group AND
 * NOT flagged `hidden_from_picker`. Used by the homepage, the catalog index
 * (`/parts`), and the build-editor add-part menu — none of those should
 * surface parent groups (which are headers, not browseable categories) or
 * the admin-only `misc` row.
 */
export async function listCategoriesWithCounts(): Promise<CategorySummary[]> {
  const rows = await db
    .select({
      slug: categories.slug,
      name: categories.name,
      partCount: sql<number>`count(${parts.id})::int`,
    })
    .from(categories)
    .leftJoin(parts, eq(parts.categoryId, categories.id))
    .where(and(isNotNull(categories.parentId), eq(categories.hiddenFromPicker, false)))
    .groupBy(categories.id, categories.slug, categories.name)
    .orderBy(categories.id);
  return rows;
}
