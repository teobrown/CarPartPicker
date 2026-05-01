import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { builds, buildItems, vehicles } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import { createBuild, getBuild, addBuildItem, removeBuildItem } from '@/lib/queries/builds';

let vehicleId: number;

beforeAll(async () => {
  await db.execute(sql`TRUNCATE TABLE build_items, builds RESTART IDENTITY CASCADE`);
  // ensure at least one vehicle exists; the seed test runs file-level beforeAll
  const v = (await db.select().from(vehicles).limit(1))[0];
  if (!v) throw new Error('vehicles must be seeded; run seed.test.ts first');
  vehicleId = v.id;
});

describe('build queries', () => {
  it('createBuild returns a build with an 8-char slug and the right vehicle', async () => {
    const b = await createBuild({ vehicleId });
    expect(b.slug).toMatch(/^[A-Za-z0-9_-]{8}$/);
    expect(b.vehicleId).toBe(vehicleId);
  });

  it('getBuild returns the build with its vehicle and zero items by default', async () => {
    const b = await createBuild({ vehicleId });
    const found = await getBuild(b.slug);
    expect(found).toBeTruthy();
    expect(found!.vehicle.id).toBe(vehicleId);
    expect(found!.items.length).toBe(0);
  });

  it('addBuildItem appends a part at the next position; removeBuildItem deletes it', async () => {
    const b = await createBuild({ vehicleId });
    // we need ANY part — insert a stub directly to keep this test self-contained
    const { parts, categories } = await import('@/lib/db/schema');
    const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p] = await db
      .insert(parts)
      .values({
        categoryId: c.id, brand: 'Test', model: 'Stub Intake',
        name: 'Test Stub Intake',
      })
      .returning();
    await addBuildItem({ buildSlug: b.slug, partId: p.id });
    let after = await getBuild(b.slug);
    expect(after!.items.length).toBe(1);
    expect(after!.items[0].part.id).toBe(p.id);
    await removeBuildItem({ buildSlug: b.slug, partId: p.id });
    after = await getBuild(b.slug);
    expect(after!.items.length).toBe(0);
  });
});
