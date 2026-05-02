import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { NextRequest } from 'next/server';
import { db } from '@/lib/db/client';
import {
  affiliateClicks,
  categories,
  parts,
  vendorListings,
  vendors,
  builds,
} from '@/lib/db/schema';
import { eq, sql } from 'drizzle-orm';
import { GET } from '@/app/go/[listingId]/route';
import { runCategorySeed } from '@/lib/db/seed/categories';
import { runVendorSeed } from '@/lib/db/seed/vendors';

let listingId: number;
let partId: number;
let vendorId: number;
let buildId: number;
let buildSlug: string;
let createdClickIds: number[] = [];

beforeAll(async () => {
  // Reset parts/listings/clicks but keep categories/vendors seeded.
  await db.execute(
    sql`TRUNCATE TABLE affiliate_clicks, vendor_listings, parts, fitment_rules RESTART IDENTITY CASCADE`,
  );
  const catCount = await db.select().from(categories).limit(1);
  if (catCount.length === 0) await runCategorySeed();
  const vendCount = await db.select().from(vendors).limit(1);
  if (vendCount.length === 0) await runVendorSeed();

  const [intake] = await db
    .select()
    .from(categories)
    .where(eq(categories.slug, 'intake'))
    .limit(1);
  // Use FCP Euro: affiliateParam='avad', affiliateValue='carpartpicker'.
  const [v] = await db
    .select()
    .from(vendors)
    .where(eq(vendors.slug, 'fcp-euro'))
    .limit(1);
  vendorId = v.id;

  const [p] = await db
    .insert(parts)
    .values({
      categoryId: intake.id,
      brand: 'TestBrand',
      model: 'GoRedirectTestPart',
      name: 'Go Redirect Test Part',
    })
    .returning();
  partId = p.id;

  const [l] = await db
    .insert(vendorListings)
    .values({
      partId: p.id,
      vendorId: v.id,
      // must match the FCP Euro baseUrl host (https://www.fcpeuro.com)
      vendorUrl: 'https://www.fcpeuro.com/product',
      priceCents: 12345,
      inStock: true,
    })
    .returning();
  listingId = l.id;

  // Create a build to test ?build=<slug> attribution. Need a vehicle.
  const { vehicles } = await import('@/lib/db/schema');
  const [veh] = await db.select().from(vehicles).limit(1);
  if (!veh) throw new Error('vehicles must be seeded; run seed.test.ts first');
  buildSlug = 'gotest01';
  const [b] = await db
    .insert(builds)
    .values({ slug: buildSlug, vehicleId: veh.id })
    .returning();
  buildId = b.id;
});

afterAll(async () => {
  // Cleanup the test rows we created so counts don't drift across runs.
  if (createdClickIds.length > 0) {
    for (const id of createdClickIds) {
      await db.delete(affiliateClicks).where(eq(affiliateClicks.id, id));
    }
  }
  // Drop the test build and listing too.
  await db.delete(affiliateClicks).where(eq(affiliateClicks.listingId, listingId));
  await db.delete(vendorListings).where(eq(vendorListings.id, listingId));
  await db.delete(parts).where(eq(parts.id, partId));
  await db.delete(builds).where(eq(builds.id, buildId));
});

async function callRoute(url: string, headers: Record<string, string> = {}) {
  const req = new NextRequest(new URL(url, 'http://localhost:3000'), {
    headers,
  });
  // Extract the listingId from the path: /go/<id>
  const m = url.match(/\/go\/([^/?]+)/);
  const idParam = m ? m[1] : '';
  return GET(req, { params: Promise.resolve({ listingId: idParam }) });
}

describe('GET /go/[listingId]', () => {
  it('returns 400 for non-numeric listing ids', async () => {
    const res = await callRoute('/go/not-a-number');
    expect(res.status).toBe(400);
  });

  it('returns 404 for unknown listing ids', async () => {
    const res = await callRoute('/go/99999999');
    expect(res.status).toBe(404);
  });

  it('returns a 302 redirect with affiliate param appended and logs a click', async () => {
    const beforeCount = await db
      .select({ c: sql<number>`count(*)::int` })
      .from(affiliateClicks);
    const before = beforeCount[0]?.c ?? 0;

    const res = await callRoute(`/go/${listingId}`, {
      'x-forwarded-for': '203.0.113.42, 10.0.0.1',
      'user-agent': 'vitest-go-test/1.0',
    });
    expect(res.status).toBe(302);
    const loc = res.headers.get('location');
    expect(loc).toBeTruthy();
    const target = new URL(loc!);
    expect(target.origin + target.pathname).toBe('https://www.fcpeuro.com/product');
    // FCP Euro vendor: affiliateParam='avad', affiliateValue='carpartpicker'
    expect(target.searchParams.get('avad')).toBe('carpartpicker');

    // Wait briefly for the fire-and-forget insert to land.
    await new Promise((r) => setTimeout(r, 250));

    const rows = await db
      .select()
      .from(affiliateClicks)
      .where(eq(affiliateClicks.listingId, listingId));
    expect(rows.length).toBe(before + 1);
    const click = rows.at(-1)!;
    expect(click.partId).toBe(partId);
    expect(click.vendorId).toBe(vendorId);
    expect(click.buildId).toBeNull();
    expect(click.userAgent).toBe('vitest-go-test/1.0');
    // ipHash should be a 32-char hex prefix of sha256('203.0.113.42').
    expect(click.ipHash).toMatch(/^[0-9a-f]{32}$/);
    createdClickIds.push(click.id);
  });

  it('attributes the click to a build when ?build=<slug> is present', async () => {
    const res = await callRoute(`/go/${listingId}?build=${buildSlug}`, {
      'user-agent': 'vitest-go-test/1.0',
    });
    expect(res.status).toBe(302);

    await new Promise((r) => setTimeout(r, 250));

    const rows = await db
      .select()
      .from(affiliateClicks)
      .where(eq(affiliateClicks.listingId, listingId));
    const lastWithBuild = rows.find((r) => r.buildId === buildId);
    expect(lastWithBuild, 'expected a click row with buildId set').toBeTruthy();
    if (lastWithBuild) createdClickIds.push(lastWithBuild.id);
  });

  it('refuses to redirect to a hostname that does not match the vendor baseUrl', async () => {
    // Insert a poisoned listing whose vendor_url points at evil.com under the
    // same vendor (FCP Euro). The /go handler must reject with a 400.
    const [intake] = await db
      .select()
      .from(categories)
      .where(eq(categories.slug, 'intake'))
      .limit(1);
    const [p] = await db
      .insert(parts)
      .values({
        categoryId: intake.id,
        brand: 'Bad',
        model: 'Listing',
        name: 'Bad Listing',
      })
      .returning();
    const [l] = await db
      .insert(vendorListings)
      .values({
        partId: p.id,
        vendorId,
        vendorUrl: 'https://evil.com/phish',
        priceCents: 1000,
        inStock: true,
      })
      .returning();
    try {
      const res = await callRoute(`/go/${l.id}`);
      expect(res.status).toBe(400);
    } finally {
      await db.delete(vendorListings).where(eq(vendorListings.id, l.id));
      await db.delete(parts).where(eq(parts.id, p.id));
    }
  });

  it('sets buildId to null when ?build=<slug> does not match a build', async () => {
    const res = await callRoute(`/go/${listingId}?build=does-not-exist`);
    expect(res.status).toBe(302);

    await new Promise((r) => setTimeout(r, 250));

    const rows = await db
      .select()
      .from(affiliateClicks)
      .where(eq(affiliateClicks.listingId, listingId));
    // The most recent row should have buildId null.
    const newest = rows.sort(
      (a, b) => new Date(b.clickedAt).getTime() - new Date(a.clickedAt).getTime(),
    )[0];
    expect(newest.buildId).toBeNull();
    createdClickIds.push(newest.id);
  });
});
