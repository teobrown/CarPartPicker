import { NextRequest } from 'next/server';
import { db } from '@/lib/db/client';
import { vendorListings, vendors, affiliateClicks, builds } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { createHash } from 'node:crypto';

function hashIp(ip: string): string {
  return createHash('sha256').update(ip).digest('hex').slice(0, 32);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ listingId: string }> },
) {
  const { listingId } = await params;
  const id = Number(listingId);
  if (!id || Number.isNaN(id)) {
    return Response.json({ error: 'bad listing id' }, { status: 400 });
  }

  const [row] = await db
    .select({
      listingId: vendorListings.id,
      partId: vendorListings.partId,
      vendorId: vendorListings.vendorId,
      vendorUrl: vendorListings.vendorUrl,
      affiliateParam: vendors.affiliateParam,
      affiliateValue: vendors.affiliateValue,
      vendorBaseUrl: vendors.baseUrl,
    })
    .from(vendorListings)
    .innerJoin(vendors, eq(vendors.id, vendorListings.vendorId))
    .where(eq(vendorListings.id, id))
    .limit(1);
  if (!row) return Response.json({ error: 'not found' }, { status: 404 });

  // Build outbound URL with affiliate code attached if known.
  let target: URL;
  try {
    target = new URL(row.vendorUrl);
  } catch {
    return Response.json({ error: 'invalid vendor url' }, { status: 500 });
  }

  // Reject open-redirect: the vendorUrl must point at the vendor's own host.
  // Subdomains of the vendor base are allowed (e.g. cdn.vendor.com).
  let baseHost: string;
  try {
    baseHost = new URL(row.vendorBaseUrl).hostname;
  } catch {
    return Response.json({ error: 'invalid vendor base url' }, { status: 500 });
  }
  if (target.hostname !== baseHost && !target.hostname.endsWith('.' + baseHost)) {
    console.warn('[/go] hostname mismatch — refusing redirect', {
      listingId: id,
      target: target.hostname,
      expected: baseHost,
    });
    return Response.json(
      { error: 'destination does not match vendor' },
      { status: 400 },
    );
  }

  if (row.affiliateParam && row.affiliateValue) {
    target.searchParams.set(row.affiliateParam, row.affiliateValue);
  }

  // Resolve ?build=<slug> to a build id for click attribution.
  const buildSlug = req.nextUrl.searchParams.get('build');
  let buildId: number | null = null;
  if (buildSlug) {
    const [b] = await db
      .select({ id: builds.id })
      .from(builds)
      .where(eq(builds.slug, buildSlug))
      .limit(1);
    if (b) buildId = b.id;
  }

  // Log click (fire-and-forget; don't block redirect on a slow insert).
  const ip = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ?? '0.0.0.0';
  const ua = req.headers.get('user-agent') ?? null;
  void db
    .insert(affiliateClicks)
    .values({
      listingId: row.listingId,
      partId: row.partId,
      vendorId: row.vendorId,
      buildId,
      ipHash: hashIp(ip),
      userAgent: ua?.slice(0, 512) ?? null,
    })
    .catch((e) => console.error('[/go] click log failed', e));

  return Response.redirect(target.toString(), 302);
}
