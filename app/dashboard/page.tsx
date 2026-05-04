import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { db } from "@/lib/db/client";
import {
  builds,
  vehicles,
  buildItems,
  vendorListings,
  users,
} from "@/lib/db/schema";
import { eq, desc, sql } from "drizzle-orm";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Your builds",
  robots: { index: false, follow: false },
};

type Row = {
  slug: string;
  vehicleLabel: string;
  generation: string;
  partCount: number;
  cheapestSumCents: number | null;
  updatedAt: Date;
};

async function listBuildsForUser(clerkId: string): Promise<Row[]> {
  const [u] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.clerkId, clerkId))
    .limit(1);
  if (!u) return [];

  // One row per build, with vehicle label + a rolled-up "cheapest available
  // total" computed as the sum of the lowest priceCents per part across all
  // its vendor listings. NULL when the build has zero items.
  const rows = await db
    .select({
      slug: builds.slug,
      year: vehicles.year,
      make: vehicles.make,
      model: vehicles.model,
      subModel: vehicles.subModel,
      generation: vehicles.generation,
      updatedAt: builds.updatedAt,
      partCount: sql<number>`(SELECT COUNT(*)::int FROM ${buildItems} WHERE ${buildItems.buildId} = ${builds.id})`,
      cheapestSumCents: sql<number | null>`(
        SELECT SUM(min_price)::bigint FROM (
          SELECT MIN(${vendorListings.priceCents}) AS min_price
          FROM ${buildItems}
          JOIN ${vendorListings} ON ${vendorListings.partId} = ${buildItems.partId}
          WHERE ${buildItems.buildId} = ${builds.id}
            AND ${vendorListings.priceCents} IS NOT NULL
          GROUP BY ${buildItems.partId}
        ) part_mins
      )`,
    })
    .from(builds)
    .innerJoin(vehicles, eq(vehicles.id, builds.vehicleId))
    .where(eq(builds.userId, u.id))
    .orderBy(desc(builds.updatedAt));

  return rows.map((r) => ({
    slug: r.slug,
    vehicleLabel: `${r.year} ${r.make} ${r.model}${r.subModel ? " " + r.subModel : ""}`,
    generation: r.generation,
    partCount: r.partCount,
    cheapestSumCents: r.cheapestSumCents,
    updatedAt: r.updatedAt,
  }));
}

export default async function DashboardPage() {
  const { userId: clerkId } = await auth();
  // Middleware already protects /dashboard, but defense in depth — if
  // somehow a request slips through unauthenticated, send to home.
  if (!clerkId) redirect("/");

  const buildsForUser = await listBuildsForUser(clerkId);

  return (
    <>
      <SiteHeader
        crumbs={[{ label: "dashboard" }]}
        liveCount={[{ label: "BUILDS", value: buildsForUser.length }]}
      />
      <main className="flex-1 mx-auto max-w-[1400px] px-6 py-12">
        <p className="eyebrow-signal mb-3">[BUILDS] · Saved to your account</p>
        <h1 className="display-lg">
          Your builds<span className="text-signal">.</span>
        </h1>

        {buildsForUser.length === 0 ? (
          <div className="mt-12 hairline p-12 text-center bg-bg-deep">
            <p className="eyebrow mb-3 text-fg-dim">[NO BUILDS]</p>
            <p className="display-md text-fg mb-2">No saved builds yet.</p>
            <p className="body-sm max-w-md mx-auto">
              Pick a vehicle on the homepage, build it out, and click{" "}
              <span className="font-[family-name:var(--font-mono)] text-fg">SAVE BUILD</span>{" "}
              at the bottom — it lands here.
            </p>
            <Link href="/" className="btn-primary mt-8 inline-flex">
              START A BUILD
            </Link>
          </div>
        ) : (
          <div className="mt-10 hairline">
            <div className="hairline-b py-3 px-5 grid grid-cols-12 gap-4 eyebrow text-[10px] bg-bg-deep">
              <span className="col-span-1">IDX</span>
              <span className="col-span-5">Vehicle</span>
              <span className="col-span-2">Parts</span>
              <span className="col-span-2 text-right">Total</span>
              <span className="col-span-2 text-right">Updated</span>
            </div>
            <ul>
              {buildsForUser.map((b, i) => (
                <li key={b.slug} className="hairline-soft-b last:border-b-0">
                  <Link
                    href={`/build/${b.slug}`}
                    className="row-hover py-4 px-5 grid grid-cols-12 gap-4 items-center"
                  >
                    <span className="col-span-1 index-marker tabular">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="col-span-5 min-w-0">
                      <span className="display-md text-base text-fg leading-tight truncate block">
                        {b.vehicleLabel}
                      </span>
                      <span className="text-[10px] tracking-[0.1em] uppercase text-fg-dim font-[family-name:var(--font-mono)]">
                        {b.generation} chassis · /{b.slug}
                      </span>
                    </span>
                    <span className="col-span-2 figure text-fg-muted">
                      ×{b.partCount}
                    </span>
                    <span className="col-span-2 figure text-right text-fg">
                      {formatPrice(b.cheapestSumCents)}
                    </span>
                    <span className="col-span-2 text-right text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                      {new Date(b.updatedAt).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
