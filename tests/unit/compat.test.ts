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
    // Caveat now includes model — "No fitment match for Volkswagen Golf R" (subModel is null).
    expect(wrx!.caveat).toBe('No fitment match for Volkswagen Golf R');
  });

  it('hideIncompatible filters out parts demoted to incompatible by the heuristic', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: vwVehicleId,
      hideIncompatible: true,
    });
    const ids = rows.map((r) => r.id);
    expect(ids).toContain(vwGolfPartId);
    expect(ids).not.toContain(subaruWrxPartId);
    for (const r of rows) expect(r.status).not.toBe('incompatible');
  });

  it('hideIncompatible is a no-op when vehicleId is null (no signal to filter on)', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: null,
      hideIncompatible: true,
    });
    // both parts return; everything is "unknown" without a vehicle context
    expect(rows.length).toBe(2);
    for (const r of rows) expect(r.status).toBe('unknown');
  });
});

describe('listCategoryPartsRankedForVehicle year-aware rules', () => {
  let intakeCategoryId: number;
  let mustang2020GtId: number;
  let mustang2003GtId: number;
  let oldMustangPartId: number;
  let multiYearMustangPartId: number;
  let subaruOnlyPartId: number;
  let vendorIdLocal: number;

  beforeAll(async () => {
    await db.execute(
      sql`TRUNCATE TABLE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`,
    );

    const [c] = await db.select().from(categories).where(eq(categories.slug, 'catback')).limit(1);
    if (!c) throw new Error('categories must be seeded; run seed.test.ts first');
    intakeCategoryId = c.id;

    const mustangs = await db.select().from(vehicles).where(eq(vehicles.model, 'Mustang')).limit(100);
    const m2020 = mustangs.find((m) => m.subModel === 'GT' && m.year === 2020);
    // 2003 isn't in seeds (S550 starts 2015), but 2017 GT is. Use 2017 as the "in-range" stand-in.
    // The point is: same model, year inside the rule range.
    const mInRange = mustangs.find((m) => m.subModel === 'GT' && m.year === 2017);
    if (!m2020 || !mInRange) {
      throw new Error('Mustang GT 2020 + 2017 must be seeded');
    }
    mustang2020GtId = m2020.id;
    mustang2003GtId = mInRange.id;

    const [vendor] = await db.select().from(vendors).where(eq(vendors.slug, 'americanmuscle')).limit(1);
    vendorIdLocal = vendor.id;

    const inserted = await db
      .insert(parts)
      .values([
        {
          categoryId: intakeCategoryId,
          brand: 'C&L',
          model: 'Cat-Back',
          name: 'C&L Cat-Back Exhaust with Polished Tips (99-04 Mustang GT, Mach 1)',
        },
        {
          categoryId: intakeCategoryId,
          brand: 'Roush',
          model: 'Cat-Back',
          name: 'Roush Cat-Back Exhaust (Mustang GT)',
        },
        {
          categoryId: intakeCategoryId,
          brand: 'Cobb',
          model: 'Cat-Back',
          name: 'Cobb Cat-Back (2008-2014 Subaru WRX)',
        },
      ])
      .returning();
    oldMustangPartId = inserted[0].id;
    multiYearMustangPartId = inserted[1].id;
    subaruOnlyPartId = inserted[2].id;

    for (const p of inserted) {
      await db.insert(vendorListings).values({
        partId: p.id,
        vendorId: vendorIdLocal,
        vendorUrl: `https://example.com/${p.id}`,
        priceCents: 30000,
        inStock: true,
      });
    }

    // Old Mustang part: rule says 1999-2004 ONLY.
    await db.insert(fitmentRules).values({
      partId: oldMustangPartId,
      make: 'Ford',
      model: 'Mustang',
      yearStart: 1999,
      yearEnd: 2004,
      status: 'fits',
      source: 'test',
    });

    // Multi-year Mustang: rules for two non-overlapping ranges. 2017 is in range; 2020 is not.
    await db.insert(fitmentRules).values([
      {
        partId: multiYearMustangPartId,
        make: 'Ford',
        model: 'Mustang',
        yearStart: 1999,
        yearEnd: 2004,
        status: 'fits',
        source: 'test',
      },
      {
        partId: multiYearMustangPartId,
        make: 'Ford',
        model: 'Mustang',
        yearStart: 2015,
        yearEnd: 2017,
        status: 'fits',
        source: 'test',
      },
    ]);

    // Subaru-only part: rule for WRX. For a Mustang vehicle there's no Mustang rule
    // — should fall through to the heuristic, not be force-marked incompatible.
    await db.insert(fitmentRules).values({
      partId: subaruOnlyPartId,
      make: 'Subaru',
      model: 'WRX',
      yearStart: 2008,
      yearEnd: 2014,
      status: 'fits',
      source: 'test',
    });
  });

  it('out-of-range year on a same-model rule marks the part incompatible', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
    });
    const old = rows.find((r) => r.id === oldMustangPartId);
    expect(old?.status).toBe('incompatible');
    expect(old?.caveat).toMatch(/1999.?2004/);
  });

  it('matches when the vehicle year falls inside any rule range', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2003GtId,
    });
    const multi = rows.find((r) => r.id === multiYearMustangPartId);
    expect(multi?.status).toBe('fits');
  });

  it('respects multi-range rules — out-of-range year still incompatible even with sibling matching range', async () => {
    // For 2020: neither 1999-2004 nor 2015-2017 contains 2020 → incompatible (the
    // part has Mustang rules and your year isn't in any of them).
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
    });
    const multi = rows.find((r) => r.id === multiYearMustangPartId);
    expect(multi?.status).toBe('incompatible');
  });

  it('hideIncompatible filters year-mismatched rule parts', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
      hideIncompatible: true,
    });
    const ids = rows.map((r) => r.id);
    expect(ids).not.toContain(oldMustangPartId);
  });

  it('rule "fits" is demoted when part name explicitly names a different sub-model', async () => {
    // Inject a part whose rule says it fits Mustang 2018-2023 (no sub-model
    // differentiation) but whose name says "Mustang GT". For an Ecoboost
    // vehicle the rule alone would match (model+year ok), but the heuristic
    // model-conflict check on "Mustang GT" must demote it.
    const [extra] = await db
      .insert(parts)
      .values({
        categoryId: intakeCategoryId,
        brand: 'Roush',
        model: 'Cold Air Intake',
        name: 'Roush Cold Air Intake (18-23 Mustang GT)',
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: extra.id,
      vendorId: vendorIdLocal,
      vendorUrl: `https://example.com/${extra.id}`,
      priceCents: 30000,
      inStock: true,
    });
    await db.insert(fitmentRules).values({
      partId: extra.id,
      make: 'Ford',
      model: 'Mustang',
      yearStart: 2018,
      yearEnd: 2023,
      status: 'fits',
      source: 'test',
    });

    const ecoVehicle = await db
      .select()
      .from(vehicles)
      .where(eq(vehicles.model, 'Mustang'))
      .limit(50);
    const eco = ecoVehicle.find((m) => m.subModel === 'Ecoboost' && m.year === 2020);
    if (!eco) throw new Error('Mustang Ecoboost 2020 must be seeded');
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: eco.id,
    });
    const row = rows.find((r) => r.id === extra.id);
    expect(row?.status).toBe('incompatible');
    expect(row?.caveat).toMatch(/match.*Mustang Ecoboost/);
  });

  it('rules for a different make+model do NOT lock the part to incompatible — heuristic still runs', async () => {
    // Subaru-only part for a Mustang vehicle: no Mustang rule → falls to
    // heuristic. "Subaru WRX" in name is not in Ford's MAKE_SYNONYMS, so the
    // heuristic returns incompatible, but with the no-fitment-match caveat,
    // not the year-mismatch caveat — proving Stage 2 didn't fire.
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
    });
    const sub = rows.find((r) => r.id === subaruOnlyPartId);
    expect(sub?.status).toBe('incompatible');
    expect(sub?.caveat).toMatch(/No fitment match/);
  });

  it('shared-fit name (GT/V6/EcoBoost) is NOT demoted by the conflict heuristic', async () => {
    // Codex critical: a multi-platform part name like "Steeda S550 Mustang
    // GT/V6/EcoBoost Springs" hits both a positive (ecoboost) and negative
    // (mustang gt) synonym for the Ecoboost vehicle. We trust the rule and
    // do not demote — only an unambiguous opposite-only name should demote.
    const [shared] = await db
      .insert(parts)
      .values({
        categoryId: intakeCategoryId,
        brand: 'Steeda',
        model: 'Lowering Springs',
        name: 'Steeda S550 Mustang GT/V6/EcoBoost Lowering Springs',
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: shared.id,
      vendorId: vendorIdLocal,
      vendorUrl: `https://example.com/${shared.id}`,
      priceCents: 30000,
      inStock: true,
    });
    await db.insert(fitmentRules).values({
      partId: shared.id,
      make: 'Ford',
      model: 'Mustang',
      yearStart: 2015,
      yearEnd: 2023,
      status: 'fits',
      source: 'test',
    });

    const allMustangs = await db.select().from(vehicles).where(eq(vehicles.model, 'Mustang')).limit(50);
    const eco2020 = allMustangs.find((m) => m.subModel === 'Ecoboost' && m.year === 2020);
    if (!eco2020) throw new Error('Mustang Ecoboost 2020 must be seeded');

    const ecoRows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: eco2020.id,
    });
    const gtRows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2003GtId, // 2017 GT, in range
    });
    expect(ecoRows.find((r) => r.id === shared.id)?.status).toBe('fits');
    expect(gtRows.find((r) => r.id === shared.id)?.status).toBe('fits');
  });

  it('caveat strings filter out garbage trims_included tokens', async () => {
    // Codex medium #2: the caveat should not surface raw LLM noise like
    // "Department of Transportation" or "max-width: 769px".
    const [noisy] = await db
      .insert(parts)
      .values({
        categoryId: intakeCategoryId,
        brand: 'Test',
        model: 'Old Mustang Part',
        name: 'Test Old Mustang Part',
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: noisy.id,
      vendorId: vendorIdLocal,
      vendorUrl: `https://example.com/${noisy.id}`,
      priceCents: 30000,
      inStock: true,
    });
    await db.insert(fitmentRules).values({
      partId: noisy.id,
      make: 'Ford',
      model: 'Mustang',
      yearStart: 1999,
      yearEnd: 2004,
      trimsIncluded: ['Department of Transportation', 'max-width: 769px', '2024-2026'],
      status: 'fits',
      source: 'test',
    });

    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
    });
    const row = rows.find((r) => r.id === noisy.id);
    expect(row?.status).toBe('incompatible');
    expect(row?.caveat).toMatch(/1999.?2004/);
    expect(row?.caveat).not.toMatch(/Department of Transportation|max-width|2024-2026/);
  });

  it('null model rules do NOT lock unrelated years to incompatible (Stage 2 only fires on explicit model claim)', async () => {
    // Codex medium #3: a generic "fits some Ford" rule (model=null) shouldn't
    // be treated as claiming Mustang. For an out-of-range year, the part
    // should fall through to the heuristic, not be force-marked incompatible.
    const [generic] = await db
      .insert(parts)
      .values({
        categoryId: intakeCategoryId,
        brand: 'Generic',
        model: 'Ford Filter',
        name: 'Generic Ford Filter Mustang Compatible',
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: generic.id,
      vendorId: vendorIdLocal,
      vendorUrl: `https://example.com/${generic.id}`,
      priceCents: 30000,
      inStock: true,
    });
    // make=Ford, model=null, year out of range
    await db.insert(fitmentRules).values({
      partId: generic.id,
      make: 'Ford',
      model: null,
      yearStart: 1999,
      yearEnd: 2004,
      status: 'fits',
      source: 'test',
    });

    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: mustang2020GtId,
    });
    const row = rows.find((r) => r.id === generic.id);
    // Heuristic catches "Mustang" in name → "unknown", NOT incompatible-by-rule.
    expect(row?.status).toBe('unknown');
  });

  it('trim filter recognizes seeded trims (Touring, High Performance, etc.)', async () => {
    // Codex low #4: REAL_TRIM_PATTERN must include trims actually in seed.
    // Build a Civic Type R rule with trims=['Touring'] and verify a Touring
    // vehicle does NOT match. Civic Type R seeds use Base/Premium, not
    // Touring — so a 2024 Type R should NOT match a Touring-only rule.
    const [trimPart] = await db
      .insert(parts)
      .values({
        categoryId: intakeCategoryId,
        brand: 'Test',
        model: 'Touring-Only',
        name: 'Test Touring-Only Civic Part',
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: trimPart.id,
      vendorId: vendorIdLocal,
      vendorUrl: `https://example.com/${trimPart.id}`,
      priceCents: 30000,
      inStock: true,
    });
    await db.insert(fitmentRules).values({
      partId: trimPart.id,
      make: 'Honda',
      model: 'Civic Type R',
      yearStart: 2023,
      yearEnd: 2026,
      trimsIncluded: ['Touring'],
      status: 'fits',
      source: 'test',
    });

    const tr = await db
      .select()
      .from(vehicles)
      .where(eq(vehicles.model, 'Civic Type R'))
      .limit(1);
    if (!tr[0]) throw new Error('Civic Type R must be seeded');
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'catback',
      vehicleId: tr[0].id,
    });
    const row = rows.find((r) => r.id === trimPart.id);
    // 'Touring' is now canonical → enforced. Type R seeded trims are
    // Base/Premium, so the rule should NOT match → incompatible via Stage 2.
    expect(row?.status).toBe('incompatible');
  });
});

describe('listCategoryPartsRankedForVehicle model-aware heuristic', () => {
  let intakeCategoryId: number;
  let civicSiVehicleId: number;
  let civicTypeRVehicleId: number;
  let mustangGtVehicleId: number;
  let mustangEcoboostVehicleId: number;
  let typeRPartId: number;
  let siPartId: number;
  let mustangGtPartId: number;
  let mustangEcoboostPartId: number;
  let vendorIdLocal: number;

  beforeAll(async () => {
    await db.execute(
      sql`TRUNCATE TABLE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`,
    );

    const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    intakeCategoryId = c.id;

    const [si] = await db.select().from(vehicles).where(eq(vehicles.model, 'Civic Si')).limit(1);
    const [tr] = await db.select().from(vehicles).where(eq(vehicles.model, 'Civic Type R')).limit(1);
    const mustangs = await db.select().from(vehicles).where(eq(vehicles.model, 'Mustang')).limit(50);
    const gtRow = mustangs.find((m) => m.subModel === 'GT');
    const ecoRow = mustangs.find((m) => m.subModel === 'Ecoboost');
    if (!si || !tr || !gtRow || !ecoRow) {
      throw new Error('Civic Si/Type R + Mustang GT/Ecoboost vehicles must be seeded');
    }
    civicSiVehicleId = si.id;
    civicTypeRVehicleId = tr.id;
    mustangGtVehicleId = gtRow.id;
    mustangEcoboostVehicleId = ecoRow.id;

    const [vendor] = await db.select().from(vendors).where(eq(vendors.slug, 'rallysport-direct')).limit(1);
    vendorIdLocal = vendor.id;

    // 4 parts, NONE with fitment_rules. The heuristic alone decides.
    const inserted = await db.insert(parts).values([
      {
        categoryId: intakeCategoryId,
        brand: 'K&N Engineering',
        model: 'Performance Air Intake System',
        name: 'K&N Performance Air Intake System - 2023-2026 Honda Civic Type R',
      },
      {
        categoryId: intakeCategoryId,
        brand: 'AEM',
        model: 'Cold Air Intake',
        name: 'AEM Cold Air Intake - 2022-2024 Honda Civic Si',
      },
      {
        categoryId: intakeCategoryId,
        brand: 'Roush',
        model: 'GT Cold Air Intake',
        name: 'Roush Cold Air Intake - 2018-2023 Mustang GT',
      },
      {
        categoryId: intakeCategoryId,
        brand: 'JLT',
        model: 'Ecoboost Cold Air Intake',
        name: 'JLT Cold Air Intake - 2015-2023 Ford Mustang Ecoboost',
      },
    ]).returning();

    typeRPartId = inserted[0].id;
    siPartId = inserted[1].id;
    mustangGtPartId = inserted[2].id;
    mustangEcoboostPartId = inserted[3].id;

    for (const p of inserted) {
      await db.insert(vendorListings).values({
        partId: p.id,
        vendorId: vendorIdLocal,
        vendorUrl: `https://example.com/${p.id}`,
        priceCents: 30000,
        inStock: true,
      });
    }
  });

  it('Type R intake does NOT match Civic Si vehicle (model-aware)', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: civicSiVehicleId,
    });
    const typeR = rows.find((r) => r.id === typeRPartId);
    const si = rows.find((r) => r.id === siPartId);
    expect(typeR?.status).toBe('incompatible');
    expect(si?.status).toBe('unknown');
  });

  it('Si intake does NOT match Civic Type R vehicle (model-aware)', async () => {
    const rows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: civicTypeRVehicleId,
    });
    const typeR = rows.find((r) => r.id === typeRPartId);
    const si = rows.find((r) => r.id === siPartId);
    expect(typeR?.status).toBe('unknown');
    expect(si?.status).toBe('incompatible');
  });

  it('Mustang GT and Ecoboost intakes are mutually exclusive (sub-model-aware)', async () => {
    const gtRows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: mustangGtVehicleId,
    });
    expect(gtRows.find((r) => r.id === mustangGtPartId)?.status).toBe('unknown');
    expect(gtRows.find((r) => r.id === mustangEcoboostPartId)?.status).toBe('incompatible');

    const ecoRows = await listCategoryPartsRankedForVehicle({
      categorySlug: 'intake',
      vehicleId: mustangEcoboostVehicleId,
    });
    expect(ecoRows.find((r) => r.id === mustangGtPartId)?.status).toBe('incompatible');
    expect(ecoRows.find((r) => r.id === mustangEcoboostPartId)?.status).toBe('unknown');
  });
});
