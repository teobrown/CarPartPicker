// Playwright runs this in its own Node process (separate from `next dev`),
// so we must load DATABASE_URL from .env.local before importing the db client.
import { config } from 'dotenv';
config({ path: '.env.local' });

// For e2e, prefer TEST_DATABASE_URL when explicitly set (CI scenario).
// In local dev, the running `next dev` server uses whatever DATABASE_URL it
// was started with — set both manually if you want them to point at the same DB.
const testUrl = process.env.TEST_DATABASE_URL;
if (testUrl) {
  process.env.DATABASE_URL = testUrl;
}

import { db } from '@/lib/db/client';
import { parts, categories, vendors, vendorListings } from '@/lib/db/schema';
import { sql, eq } from 'drizzle-orm';

/**
 * Idempotent: ensures a Cobb SF Intake exists in the DB with one fcp-euro listing.
 * Re-runs cleanly if the row already exists. Used by the e2e tests to guarantee
 * something to render at /parts.
 */
export async function ensureSamplePart() {
  // Make sure category and vendor exist (re-seed if not)
  let intake = (await db.select().from(categories).where(eq(categories.slug, 'intake')).limit(1))[0];
  if (!intake) {
    [intake] = await db.insert(categories)
      .values({ name: 'Intake', slug: 'intake' })
      .returning();
  }
  let vendor = (await db.select().from(vendors).where(eq(vendors.slug, 'fcp-euro')).limit(1))[0];
  if (!vendor) {
    [vendor] = await db.insert(vendors).values({
      name: 'FCP Euro', slug: 'fcp-euro',
      affiliateProgram: 'AvantLink', affiliateParam: 'avad',
      affiliateValue: 'carbuildr', baseUrl: 'https://www.fcpeuro.com',
    }).returning();
  }
  // Find or insert the part
  let part = (await db.select().from(parts)
    .where(sql`brand = 'Cobb' AND model = 'SF Intake'`)
    .limit(1))[0];
  if (!part) {
    [part] = await db.insert(parts).values({
      categoryId: intake.id,
      brand: 'Cobb', model: 'SF Intake', name: 'Cobb SF Intake',
      msrpCents: 42500,
    }).returning();
  }
  // Find or insert one vendor listing
  const existingListing = (await db.select().from(vendorListings)
    .where(sql`part_id = ${part.id} AND vendor_id = ${vendor.id}`)
    .limit(1))[0];
  if (!existingListing) {
    await db.insert(vendorListings).values({
      partId: part.id, vendorId: vendor.id,
      vendorUrl: 'https://www.fcpeuro.com/products/cobb-sf-intake-example',
      priceCents: 42000, inStock: true,
    });
  }
}
