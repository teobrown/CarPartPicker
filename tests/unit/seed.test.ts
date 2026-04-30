import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { vehicles } from '@/lib/db/schema';
import { sql } from 'drizzle-orm';
import { runVehicleSeed } from '@/lib/db/seed/vehicles';

describe('vehicles seed', () => {
  beforeAll(async () => {
    await db.execute(sql`TRUNCATE TABLE vehicles RESTART IDENTITY CASCADE`);
    await runVehicleSeed();
  });

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
});
