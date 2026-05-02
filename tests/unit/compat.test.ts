import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { parts, categories, vendors, vendorListings, fitmentRules, vehicles } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import { listCategoryPartsRankedForVehicle } from '@/lib/queries/compat';

let categoryId: number;
let vehicleId: number;
let vehicleMake: string;
let vehicleModelName: string;
let vehicleGeneration: string;
let vendorId: number;

let unknownPartId: number;
let fittingPartId: number;
let incompatiblePartId: number;

beforeAll(async () => {
  // Truncate the part-related tables so this file owns its data deterministically.
  // CASCADE clears vendor_listings, fitment_rules, build_items.
  await db.execute(
    sql`TRUNCATE TABLE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`,
  );

  const [c] = await db
    .select()
    .from(categories)
    .where(eq(categories.slug, 'intake'))
    .limit(1);
  if (!c) throw new Error('categories must be seeded; run seed.test.ts first');
  categoryId = c.id;

  const [v] = await db
    .select()
    .from(vehicles)
    .where(eq(vehicles.model, 'WRX'))
    .limit(1);
  if (!v) throw new Error('vehicles must be seeded; run seed.test.ts first');
  vehicleId = v.id;
  vehicleMake = v.make;
  vehicleModelName = v.model;
  vehicleGeneration = v.generation;

  const [vendor] = await db
    .select()
    .from(vendors)
    .where(eq(vendors.slug, 'fcp-euro'))
    .limit(1);
  if (!vendor) throw new Error('vendors must be seeded; run seed.test.ts first');
  vendorId = vendor.id;

  // Insert deterministic parts: one with a fitting rule, one incompatible, one unknown.
  // The "unknown" part's name includes a Subaru synonym ("WRX") so the make-name
  // heuristic keeps it at status="unknown" instead of demoting to "incompatible".
  const inserted = await db
    .insert(parts)
    .values([
      { categoryId, brand: 'Cobb', model: 'SF Intake', name: 'Cobb SF Intake' },
      { categoryId, brand: 'AEM', model: 'Air Intake', name: 'AEM Air Intake' },
      { categoryId, brand: 'Generic', model: 'WRX Cone Filter', name: 'Generic WRX Cone Filter' },
    ])
    .returning();

  fittingPartId = inserted[0].id;
  incompatiblePartId = inserted[1].id;
  unknownPartId = inserted[2].id;

  // Vendor listing for each so cheapest_price_cents isn't null and they all show up.
  for (const p of inserted) {
    await db.insert(vendorListings).values({
      partId: p.id,
      vendorId,
      vendorUrl: `https://example.com/${p.id}`,
      priceCents: 30000,
      inStock: true,
    });
  }

  // Fitting rule: matches the WRX.
  await db.insert(fitmentRules).values({
    partId: fittingPartId,
    make: vehicleMake,
    model: vehicleModelName,
    generation: vehicleGeneration,
    status: 'fits',
    source: 'test',
  });

  // Incompatible rule: matches the WRX but says it does not fit.
  await db.insert(fitmentRules).values({
    partId: incompatiblePartId,
    make: vehicleMake,
    model: vehicleModelName,
    generation: vehicleGeneration,
    status: 'incompatible',
    caveat: 'wrong intake plumbing',
    source: 'test',
  });
  // The third part has no rule at all → should fall through to "unknown".
});

describe('listCategoryPartsRankedForVehicle', () => {
  it('returns parts in the given category with status "unknown" when vehicleId is null', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: null,
    });
    expect(rows.length).toBeGreaterThanOrEqual(3);
    const ids = rows.map((r) => r.id);
    expect(ids).toContain(fittingPartId);
    expect(ids).toContain(incompatiblePartId);
    expect(ids).toContain(unknownPartId);
    for (const r of rows) {
      expect(r.status).toBe('unknown');
      expect(r.caveat).toBeNull();
    }
  });

  it('ranks a fitting part above one with no matching rule for the given vehicle', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId,
    });
    const fittingIdx = rows.findIndex((r) => r.id === fittingPartId);
    const unknownIdx = rows.findIndex((r) => r.id === unknownPartId);
    const incompatibleIdx = rows.findIndex((r) => r.id === incompatiblePartId);
    expect(fittingIdx).toBeGreaterThanOrEqual(0);
    expect(unknownIdx).toBeGreaterThanOrEqual(0);
    expect(incompatibleIdx).toBeGreaterThanOrEqual(0);
    // fitting < unknown < incompatible in array index (lower index = higher rank)
    expect(fittingIdx).toBeLessThan(unknownIdx);
    expect(unknownIdx).toBeLessThan(incompatibleIdx);

    const fitting = rows[fittingIdx];
    expect(fitting.status).toBe('fits');
    const incompatible = rows[incompatibleIdx];
    expect(incompatible.status).toBe('incompatible');
    expect(incompatible.caveat).toBe('wrong intake plumbing');
  });

  it('filters by brand or model substring (case-insensitive)', async () => {
    const byBrand = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId,
      search: 'cobb',
    });
    expect(byBrand.length).toBe(1);
    expect(byBrand[0].id).toBe(fittingPartId);

    const byModel = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId,
      search: 'CONE',
    });
    expect(byModel.length).toBe(1);
    expect(byModel[0].id).toBe(unknownPartId);
  });
});

describe('listCategoryPartsRankedForVehicle make-name heuristic', () => {
  let vwCategoryId: number;
  let vwVehicleId: number;
  let vwVendorId: number;
  let vwGolfPartId: number;
  let subaruWrxPartId: number;

  beforeAll(async () => {
    // This describe block sets up its own deterministic data; truncate first.
    await db.execute(
      sql`TRUNCATE TABLE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`,
    );

    const [c] = await db
      .select()
      .from(categories)
      .where(eq(categories.slug, 'intake'))
      .limit(1);
    if (!c) throw new Error('categories must be seeded; run seed.test.ts first');
    vwCategoryId = c.id;

    // Pick any seeded VW Golf R Mk7 row.
    const [vw] = await db
      .select()
      .from(vehicles)
      .where(eq(vehicles.make, 'Volkswagen'))
      .limit(1);
    if (!vw) throw new Error('vehicles must be seeded; run seed.test.ts first');
    vwVehicleId = vw.id;

    const [vendor] = await db
      .select()
      .from(vendors)
      .where(eq(vendors.slug, 'fcp-euro'))
      .limit(1);
    if (!vendor) throw new Error('vendors must be seeded; run seed.test.ts first');
    vwVendorId = vendor.id;

    // Two parts in 'intake', NEITHER with a fitment_rules row.
    // - "Volkswagen Golf R Intake": matches MAKE_SYNONYMS for Volkswagen → stays "unknown"
    // - "Subaru WRX Intake": matches MAKE_SYNONYMS for Subaru, NOT for Volkswagen → "incompatible"
    const inserted = await db
      .insert(parts)
      .values([
        {
          categoryId: vwCategoryId,
          brand: 'APR',
          model: 'Golf R Intake',
          name: 'Volkswagen Golf R Intake',
        },
        {
          categoryId: vwCategoryId,
          brand: 'Cobb',
          model: 'WRX Intake',
          name: 'Subaru WRX Intake',
        },
      ])
      .returning();

    vwGolfPartId = inserted[0].id;
    subaruWrxPartId = inserted[1].id;

    for (const p of inserted) {
      await db.insert(vendorListings).values({
        partId: p.id,
        vendorId: vwVendorId,
        vendorUrl: `https://example.com/${p.id}`,
        priceCents: 30000,
        inStock: true,
      });
    }
    // Intentionally no fitment_rules inserted.
  });

  it('demotes parts with no rule and no make-name match to incompatible', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: vwVehicleId,
    });
    const vw = rows.find((r) => r.id === vwGolfPartId);
    const wrx = rows.find((r) => r.id === subaruWrxPartId);
    expect(vw).toBeDefined();
    expect(wrx).toBeDefined();
    expect(vw!.status).toBe('unknown');
    expect(vw!.caveat).toBeNull();
    expect(wrx!.status).toBe('incompatible');
    expect(wrx!.caveat).toBe('No fitment match for Volkswagen');
  });
});
