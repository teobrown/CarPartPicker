import { describe, it, expect, beforeAll } from 'vitest';
import { db } from '@/lib/db/client';
import { builds, buildItems, vehicles, users } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';
import {
  createBuild,
  getBuild,
  addBuildItem,
  removeBuildItem,
  BuildOwnershipError,
} from '@/lib/queries/builds';

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
    await addBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null });
    let after = await getBuild(b.slug);
    expect(after!.items.length).toBe(1);
    expect(after!.items[0].part.id).toBe(p.id);
    await removeBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null });
    after = await getBuild(b.slug);
    expect(after!.items.length).toBe(0);
  });

  it('addBuildItem replaces an existing item in the same category instead of duplicating', async () => {
    const b = await createBuild({ vehicleId });
    const { parts, categories } = await import('@/lib/db/schema');
    const [intake] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p1] = await db
      .insert(parts)
      .values({ categoryId: intake.id, brand: 'A', model: 'First Intake', name: 'A First Intake' })
      .returning();
    const [p2] = await db
      .insert(parts)
      .values({ categoryId: intake.id, brand: 'B', model: 'Second Intake', name: 'B Second Intake' })
      .returning();
    await addBuildItem({ buildSlug: b.slug, partId: p1.id, actorClerkId: null });
    await addBuildItem({ buildSlug: b.slug, partId: p2.id, actorClerkId: null });
    const after = await getBuild(b.slug);
    expect(after!.items.length).toBe(1);
    expect(after!.items[0].part.id).toBe(p2.id);
  });

  it('addBuildItem is idempotent for the same part — re-adding does not duplicate', async () => {
    const b = await createBuild({ vehicleId });
    const { parts, categories } = await import('@/lib/db/schema');
    const [intake] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p] = await db
      .insert(parts)
      .values({ categoryId: intake.id, brand: 'A', model: 'Dup Intake', name: 'A Dup Intake' })
      .returning();
    await addBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null });
    await addBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null });
    const after = await getBuild(b.slug);
    expect(after!.items.length).toBe(1);
    expect(after!.items[0].part.id).toBe(p.id);
  });
});

describe('build ownership semantics', () => {
  it('addBuildItem rejects when actor does not own a claimed build', async () => {
    // Set up a build owned by user A, then have anonymous + user-B actors
    // try to mutate it. Both should fail with BuildOwnershipError.
    const b = await createBuild({ vehicleId });
    const [userA] = await db
      .insert(users)
      .values({ clerkId: 'user_test_owner_A', email: 'a@example.test' })
      .onConflictDoUpdate({
        target: users.clerkId,
        set: { email: 'a@example.test' },
      })
      .returning();
    const [userB] = await db
      .insert(users)
      .values({ clerkId: 'user_test_other_B', email: 'b@example.test' })
      .onConflictDoUpdate({
        target: users.clerkId,
        set: { email: 'b@example.test' },
      })
      .returning();
    await db.update(builds).set({ userId: userA.id }).where(eq(builds.id, b.id));

    const { parts, categories } = await import('@/lib/db/schema');
    const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p] = await db
      .insert(parts)
      .values({ categoryId: c.id, brand: 'X', model: 'Owner Test Part', name: 'Owner Test Part' })
      .returning();

    // Anonymous actor — not owner.
    await expect(
      addBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null }),
    ).rejects.toBeInstanceOf(BuildOwnershipError);

    // Different signed-in user — not owner.
    await expect(
      addBuildItem({
        buildSlug: b.slug,
        partId: p.id,
        actorClerkId: 'user_test_other_B',
      }),
    ).rejects.toBeInstanceOf(BuildOwnershipError);

    // Build remains empty since both attempts were rejected.
    const after = await getBuild(b.slug);
    expect(after!.items.length).toBe(0);

    // Owner can edit.
    await addBuildItem({
      buildSlug: b.slug,
      partId: p.id,
      actorClerkId: 'user_test_owner_A',
    });
    const final = await getBuild(b.slug);
    expect(final!.items.length).toBe(1);

    // Cleanup so other tests aren't affected — the userB var is referenced
    // here so the linter doesn't warn about an unused declaration; the row
    // exists only so the second rejection is a real "different user" case
    // rather than "user not yet provisioned".
    expect(userB.clerkId).toBe('user_test_other_B');
  });

  it('removeBuildItem rejects non-owners on claimed builds', async () => {
    const b = await createBuild({ vehicleId });
    const [u] = await db
      .insert(users)
      .values({ clerkId: 'user_test_remove_owner', email: 'r@example.test' })
      .onConflictDoUpdate({
        target: users.clerkId,
        set: { email: 'r@example.test' },
      })
      .returning();
    await db.update(builds).set({ userId: u.id }).where(eq(builds.id, b.id));

    const { parts, categories } = await import('@/lib/db/schema');
    const [c] = await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1);
    const [p] = await db
      .insert(parts)
      .values({ categoryId: c.id, brand: 'Y', model: 'Remove Owner Part', name: 'Remove Owner Part' })
      .returning();
    await addBuildItem({
      buildSlug: b.slug,
      partId: p.id,
      actorClerkId: 'user_test_remove_owner',
    });

    await expect(
      removeBuildItem({ buildSlug: b.slug, partId: p.id, actorClerkId: null }),
    ).rejects.toBeInstanceOf(BuildOwnershipError);
  });
});
