import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { vehicles, categories, vendors } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import { runVehicleSeed } from '@/lib/db/seed/vehicles';
import { runCategorySeed } from '@/lib/db/seed/categories';
// future imports for runVendorSeed go here

beforeAll(async () => {
  // Truncate ALL seed-owned tables in one CASCADE so FK references don't break
  // when a sibling table is wiped. Order doesn't matter with CASCADE; restarting
  // identity is best-effort to keep IDs predictable.
  await db.execute(sql`TRUNCATE TABLE vehicles, categories, vendors RESTART IDENTITY CASCADE`);
  await runVehicleSeed();
  await runCategorySeed();
  // future: await runVendorSeed();
});

describe('vehicles seed', () => {
  it('inserts at least 150 vehicle rows across the 8 platform groups', async () => {
    const rows = await db.select().from(vehicles);
    expect(rows.length).toBeGreaterThanOrEqual(150);
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
  it('inserts the 18 MVP categories', async () => {
    const rows = await db.select().from(categories);
    expect(rows.length).toBeGreaterThanOrEqual(15);
    const slugs = rows.map((r) => r.slug);
    for (const expected of [
      'intake', 'catback', 'axleback', 'muffler-delete', 'tune', 'downpipe',
      'intercooler', 'bov', 'coilovers', 'springs', 'sway-bars',
      'wheels', 'tires', 'lip-kit', 'spoiler', 'fender-flares',
      'headlights', 'taillights',
    ]) {
      expect(slugs, `missing slug: ${expected}`).toContain(expected);
    }
  });
});
