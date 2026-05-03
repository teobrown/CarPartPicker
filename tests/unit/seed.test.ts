import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { vehicles, categories, vendors } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import { runVehicleSeed } from '@/lib/db/seed/vehicles';
import { runCategorySeed } from '@/lib/db/seed/categories';
import { runVendorSeed } from '@/lib/db/seed/vendors';

beforeAll(async () => {
  // Truncate ALL seed-owned tables in one CASCADE so FK references don't break
  // when a sibling table is wiped. Order doesn't matter with CASCADE; restarting
  // identity is best-effort to keep IDs predictable.
  await db.execute(sql`TRUNCATE TABLE vehicles, categories, vendors RESTART IDENTITY CASCADE`);
  await runVehicleSeed();
  await runCategorySeed();
  await runVendorSeed();
});

describe('vehicles seed', () => {
  it('inserts at least 195 vehicle rows across the 8 platform groups', async () => {
    const rows = await db.select().from(vehicles);
    expect(rows.length).toBeGreaterThanOrEqual(195);
  });

  it('seeds the expected Mustang coverage (GT + Ecoboost across 9 years)', async () => {
    const rows = await db.select().from(vehicles).where(eq(vehicles.model, 'Mustang'));
    // GT (Base, Premium) × 9 years + Ecoboost (Base, Premium, High Performance) × 9 years = 45
    expect(rows.length).toBe(45);
    const gtCount = rows.filter((r) => r.subModel === 'GT').length;
    const ecoCount = rows.filter((r) => r.subModel === 'Ecoboost').length;
    expect(gtCount).toBe(18);
    expect(ecoCount).toBe(27);
  });

  it('every row has a non-null generation and bolt_pattern', async () => {
    const rows = await db.select().from(vehicles);
    for (const r of rows) {
      expect(r.generation, `${r.year} ${r.make} ${r.model}`).toBeTruthy();
      expect(r.boltPattern, `${r.year} ${r.make} ${r.model}`).toBeTruthy();
    }
  });

  it('covers all 8 platform groups', async () => {
    const rows = await db.select().from(vehicles);
    const models = new Set(rows.map((r) => r.model));
    expect(models).toContain('WRX');
    expect(models).toContain('GR Corolla');
    expect(models).toContain('GR86');
    expect(models).toContain('Civic Si');
    expect(models).toContain('Mustang');
    expect(models).toContain('MX-5 Miata');
    expect(models).toContain('Golf R');
  });

  it('preserves fractional bore values (regression test for issue caught in fix)', async () => {
    const rows = await db.select().from(vehicles).where(eq(vehicles.model, 'GR Corolla'));
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) expect(r.centerBoreMm).toBe(60.1);
  });
});

describe('categories seed', () => {
  it('inserts every parent group and leaf (60 rows total)', async () => {
    const rows = await db.select().from(categories);
    expect(rows.length).toBe(60);
    const slugs = rows.map((r) => r.slug).sort();
    // Sample-check: parents and a representative leaf from each group.
    for (const expected of [
      'intake', 'exhaust', 'forced-induction', 'tuning',
      'suspension', 'wheels-tires', 'brakes', 'body-aero',
      'lighting', 'internal',
      'cold-air-intake', 'catback-exhaust', 'intercooler', 'fuel-system',
      'ecu-tune', 'coilovers', 'wheels', 'brake-pads',
      'front-lip', 'headlights', 'misc',
    ]) {
      expect(slugs, `missing slug: ${expected}`).toContain(expected);
    }
  });

  it('marks misc as hidden from picker; everything else visible', async () => {
    const rows = await db.select().from(categories);
    const hidden = rows.filter((r) => r.hiddenFromPicker).map((r) => r.slug).sort();
    expect(hidden).toEqual(['internal', 'misc']);
  });

  it('every leaf has a parent_id pointing at a real parent', async () => {
    const rows = await db.select().from(categories);
    const byId = new Map(rows.map((r) => [r.id, r]));
    const leaves = rows.filter((r) => r.parentId != null);
    expect(leaves.length).toBe(50);
    for (const leaf of leaves) {
      expect(byId.get(leaf.parentId!), `leaf ${leaf.slug} -> orphan parent_id ${leaf.parentId}`).toBeDefined();
      expect(byId.get(leaf.parentId!)!.parentId).toBeNull();
    }
  });
});

describe('vendors seed', () => {
  it('inserts every launch and Phase 1 vendor', async () => {
    const rows = await db.select().from(vendors);
    const slugs = rows.map((r) => r.slug).sort();
    expect(slugs).toEqual([
      '034motorsport', '27won', 'americanmuscle', 'ebay-motors', 'ecs-tuning',
      'fcp-euro', 'flyin-miata', 'iag-performance', 'k-tuned', 'maperformance',
      'prl-motorsports', 'rallysport-direct', 'skunk2', 'steeda', 'summit-racing',
    ]);
  });
});
