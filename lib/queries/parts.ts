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
