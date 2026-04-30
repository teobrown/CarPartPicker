import { db } from '@/lib/db/client';
import { parts, categories, vendorListings } from '@/lib/db/schema';
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
