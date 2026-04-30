import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { parts, categories, vendorListings, vendors } from '@/lib/db/schema';
import { sql } from 'drizzle-orm';
import { listPartsByCategory, listAllParts, getPartByBrandModel } from '@/lib/queries/parts';
import { runCategorySeed } from '@/lib/db/seed/categories';
import { runVendorSeed } from '@/lib/db/seed/vendors';

describe('parts queries', () => {
  beforeAll(async () => {
    // Clean slate for parts/listings, but keep categories and vendors seeded.
    // Re-seed categories/vendors defensively in case a sibling test truncated
    // them via CASCADE.
    await db.execute(sql`TRUNCATE parts, vendor_listings, fitment_rules RESTART IDENTITY CASCADE`);
    const catCount = await db.select().from(categories).limit(1);
    if (catCount.length === 0) await runCategorySeed();
    const vendCount = await db.select().from(vendors).limit(1);
    if (vendCount.length === 0) await runVendorSeed();

    const [intake] = await db.select().from(categories).where(sql`slug = 'intake'`).limit(1);
    const [v] = await db.select().from(vendors).where(sql`slug = 'fcp-euro'`).limit(1);
    const [p] = await db
      .insert(parts)
      .values({
        categoryId: intake.id,
        brand: 'Cobb',
        model: 'SF Intake',
        name: 'Cobb SF Intake',
        msrpCents: 42500,
      })
      .returning();
    await db.insert(vendorListings).values({
      partId: p.id,
      vendorId: v.id,
      vendorUrl: 'https://example.com',
      priceCents: 42000,
      inStock: true,
    });
  });

  it('listAllParts returns at least 1 row with the cheapest listing price', async () => {
    const rows = await listAllParts();
    expect(rows.length).toBeGreaterThan(0);
    const cobb = rows.find((r) => r.brand === 'Cobb' && r.model === 'SF Intake');
    expect(cobb).toBeDefined();
    expect(cobb!.cheapestPriceCents).toBe(42000);
  });

  it('listPartsByCategory filters by category slug', async () => {
    const intakeRows = await listPartsByCategory('intake');
    expect(intakeRows.every((r) => r.categorySlug === 'intake')).toBe(true);
    const exhaustRows = await listPartsByCategory('catback');
    expect(exhaustRows.length).toBe(0);
  });

  it('getPartByBrandModel returns the part with all vendor listings', async () => {
    const found = await getPartByBrandModel('cobb', 'sf-intake');
    expect(found).toBeDefined();
    expect(found!.brand).toBe('Cobb');
    expect(found!.listings.length).toBeGreaterThan(0);
  });
});
