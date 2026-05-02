import { db } from '@/lib/db/client';
import { builds, buildItems, parts, categories, vehicles, vendorListings } from '@/lib/db/schema';
import { eq, sql } from 'drizzle-orm';
import { newBuildSlug } from '@/lib/slug';

export type BuildItemRow = {
  position: number;
  userNote: string | null;
  part: {
    id: number;
    brand: string;
    model: string;
    name: string;
    categorySlug: string;
    cheapestPriceCents: number | null;
    vendorCount: number;
  };
};

export type BuildDetail = {
  id: number;
  slug: string;
  createdAt: Date;
  vehicle: {
    id: number;
    make: string;
    model: string;
    year: number;
    trim: string | null;
    subModel: string | null;
    generation: string;
  };
  items: BuildItemRow[];
};

export async function createBuild(opts: { vehicleId: number }): Promise<{ id: number; slug: string; vehicleId: number }> {
  // retry on collision (shouldn't happen but cheap insurance)
  for (let attempt = 0; attempt < 5; attempt++) {
    const slug = newBuildSlug();
    try {
      const [row] = await db
        .insert(builds)
        .values({ slug, vehicleId: opts.vehicleId })
        .returning({ id: builds.id, slug: builds.slug, vehicleId: builds.vehicleId });
      return row;
    } catch (e) {
      // unique violation; loop and try a new slug
      if (attempt === 4) throw e;
    }
  }
  throw new Error('unreachable');
}

export async function getBuild(slug: string): Promise<BuildDetail | null> {
  const [b] = await db
    .select({
      id: builds.id,
      slug: builds.slug,
      createdAt: builds.createdAt,
      vehicleId: vehicles.id,
      make: vehicles.make,
      model: vehicles.model,
      year: vehicles.year,
      trim: vehicles.trim,
      subModel: vehicles.subModel,
      generation: vehicles.generation,
    })
    .from(builds)
    .innerJoin(vehicles, eq(vehicles.id, builds.vehicleId))
    .where(eq(builds.slug, slug))
    .limit(1);
  if (!b) return null;

  const itemRows = await db
    .select({
      position: buildItems.position,
      userNote: buildItems.userNote,
      partId: parts.id,
      brand: parts.brand,
      partModel: parts.model,
      name: parts.name,
      categorySlug: categories.slug,
    })
    .from(buildItems)
    .innerJoin(parts, eq(parts.id, buildItems.partId))
    .innerJoin(categories, eq(categories.id, parts.categoryId))
    .where(eq(buildItems.buildId, b.id))
    .orderBy(buildItems.position);

  // attach pricing per part
  const items: BuildItemRow[] = await Promise.all(
    itemRows.map(async (r) => {
      const listings = await db
        .select({ priceCents: vendorListings.priceCents, vendorId: vendorListings.vendorId })
        .from(vendorListings)
        .where(eq(vendorListings.partId, r.partId));
      const cheapest = listings.reduce<number | null>((acc, l) => {
        if (l.priceCents == null) return acc;
        return acc == null || l.priceCents < acc ? l.priceCents : acc;
      }, null);
      const vendorCount = new Set(listings.map((l) => l.vendorId)).size;
      return {
        position: r.position,
        userNote: r.userNote,
        part: {
          id: r.partId,
          brand: r.brand,
          model: r.partModel,
          name: r.name,
          categorySlug: r.categorySlug,
          cheapestPriceCents: cheapest,
          vendorCount,
        },
      };
    }),
  );

  return {
    id: b.id,
    slug: b.slug,
    createdAt: b.createdAt,
    vehicle: {
      id: b.vehicleId,
      make: b.make,
      model: b.model,
      year: b.year,
      trim: b.trim,
      subModel: b.subModel,
      generation: b.generation,
    },
    items,
  };
}

export async function addBuildItem(opts: { buildSlug: string; partId: number; note?: string | null }): Promise<void> {
  const [b] = await db.select({ id: builds.id }).from(builds).where(eq(builds.slug, opts.buildSlug)).limit(1);
  if (!b) throw new Error(`build not found: ${opts.buildSlug}`);

  // Look up the new part's category so we can replace any existing item in
  // the same category — PCPartPicker semantics: one part per category slot.
  // Also handles dup-click races (second insert overwrites the first).
  const [partRow] = await db
    .select({ id: parts.id, categoryId: parts.categoryId })
    .from(parts)
    .where(eq(parts.id, opts.partId))
    .limit(1);
  if (!partRow) throw new Error(`part not found: ${opts.partId}`);

  await db.transaction(async (tx) => {
    await tx
      .delete(buildItems)
      .where(
        sql`${buildItems.buildId} = ${b.id} AND ${buildItems.partId} IN (SELECT id FROM parts WHERE category_id = ${partRow.categoryId})`,
      );
    const [{ next }] = await tx
      .select({ next: sql<number>`COALESCE(MAX(${buildItems.position}), 0) + 1` })
      .from(buildItems)
      .where(eq(buildItems.buildId, b.id));
    await tx.insert(buildItems).values({
      buildId: b.id,
      partId: opts.partId,
      position: next,
      userNote: opts.note ?? null,
    });
    await tx.update(builds).set({ updatedAt: new Date() }).where(eq(builds.id, b.id));
  });
}

export async function removeBuildItem(opts: { buildSlug: string; partId: number }): Promise<void> {
  const [b] = await db.select({ id: builds.id }).from(builds).where(eq(builds.slug, opts.buildSlug)).limit(1);
  if (!b) throw new Error(`build not found: ${opts.buildSlug}`);
  await db.delete(buildItems).where(sql`${buildItems.buildId} = ${b.id} AND ${buildItems.partId} = ${opts.partId}`);
  await db.update(builds).set({ updatedAt: new Date() }).where(eq(builds.id, b.id));
}
