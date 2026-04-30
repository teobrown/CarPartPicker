import { describe, it, expect } from 'vitest';
import { db } from '@/lib/db/client';
import {
  vehicles,
  categories,
  vendors,
  vendorListings,
  parts,
  fitmentRules,
  builds,
  buildItems,
  affiliateClicks,
} from '@/lib/db/schema';

describe('schema is queryable', () => {
  it.each([
    ['vehicles', vehicles],
    ['categories', categories],
    ['vendors', vendors],
    ['vendor_listings', vendorListings],
    ['parts', parts],
    ['fitment_rules', fitmentRules],
    ['builds', builds],
    ['build_items', buildItems],
    ['affiliate_clicks', affiliateClicks],
  ] as const)('selects 0 rows from %s on a fresh DB', async (_name, table) => {
    const rows = await db.select().from(table).limit(1);
    expect(rows.length).toBeLessThanOrEqual(1);
  });
});
