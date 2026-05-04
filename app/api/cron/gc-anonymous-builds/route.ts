import { db } from "@/lib/db/client";
import { builds, buildItems } from "@/lib/db/schema";
import { sql, isNull, and, lt, notInArray } from "drizzle-orm";

// Daily cron — bound the growth of the builds table by garbage-collecting
// anonymous builds that have outlived their usefulness. Codex review-6
// flagged POST /api/builds as an unbounded write-amplification DoS vector;
// this endpoint closes the bound by ensuring no anonymous build can persist
// indefinitely.
//
// Two-tier policy:
//   1. EMPTY anonymous builds (zero buildItems) older than 24h are
//      deleted unconditionally. These are typically spam-creates or
//      "user picked vehicle, walked away, never added a part" sessions.
//   2. NON-EMPTY anonymous builds (at least one part picked) older than
//      60 days are deleted. Generous TTL so real users have time to come
//      back, but still bounded.
//
// Authentication: Vercel Cron sets `Authorization: Bearer $CRON_SECRET`
// on every cron-triggered invocation. We require a matching CRON_SECRET
// env var so a public POST can't trigger the GC. Returns 401 otherwise.
//
// build_items has ON DELETE CASCADE on buildId, so removing a build also
// drops its items — no separate cleanup needed.

const EMPTY_TTL_HOURS = 24;
const ITEMED_TTL_DAYS = 60;

export async function GET(req: Request) {
  const expected = process.env.CRON_SECRET;
  if (!expected) {
    return Response.json({ error: "CRON_SECRET not configured" }, { status: 500 });
  }
  const auth = req.headers.get("authorization");
  if (auth !== `Bearer ${expected}`) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  // Tier 1: empty anonymous builds older than EMPTY_TTL_HOURS.
  const emptyResult = await db
    .delete(builds)
    .where(
      and(
        isNull(builds.userId),
        lt(builds.createdAt, sql`NOW() - INTERVAL '${sql.raw(String(EMPTY_TTL_HOURS))} hours'`),
        notInArray(
          builds.id,
          db.selectDistinct({ id: buildItems.buildId }).from(buildItems),
        ),
      ),
    )
    .returning({ id: builds.id });

  // Tier 2: non-empty anonymous builds older than ITEMED_TTL_DAYS.
  const itemedResult = await db
    .delete(builds)
    .where(
      and(
        isNull(builds.userId),
        lt(builds.createdAt, sql`NOW() - INTERVAL '${sql.raw(String(ITEMED_TTL_DAYS))} days'`),
      ),
    )
    .returning({ id: builds.id });

  return Response.json({
    deletedEmpty: emptyResult.length,
    deletedItemed: itemedResult.length,
  });
}

// Keep the route from being statically optimized — must run server-side
// every cron invocation, never cached.
export const dynamic = "force-dynamic";
