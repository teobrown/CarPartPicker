import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { auth } from '@clerk/nextjs/server';
import { db } from '@/lib/db/client';
import { users } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { getBuild } from '@/lib/queries/builds';
import { listCategoriesGrouped } from '@/lib/queries/parts';
import { listCategoryPartsRankedForVehicle, type CompatStatus } from '@/lib/queries/compat';
import { SiteHeader } from '@/app/components/site-header';
import { SiteFooter } from '@/app/components/site-footer';
import { BuildRow } from '@/app/components/build-row';
import { BuildSummary } from '@/app/components/build-summary';
import { BuildActions } from '@/app/components/build-actions';

export const dynamic = 'force-dynamic';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const build = await getBuild(slug);
  if (!build) {
    return {
      title: 'Build not found',
      robots: { index: false, follow: false },
    };
  }
  const title = `${build.vehicle.year} ${build.vehicle.make} ${build.vehicle.model} build`;
  return {
    title,
    description: `Anonymous build for a ${build.vehicle.year} ${build.vehicle.make} ${build.vehicle.model} — ${build.items.length} part${build.items.length === 1 ? '' : 's'} selected.`,
    robots: { index: false, follow: false },
  };
}

export default async function BuildPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const build = await getBuild(slug);
  if (!build) return notFound();

  // Resolve current user ownership of this build for the action buttons.
  // - currentUserOwns is true only when signed-in user's local users.id
  //   matches builds.user_id. Stays false for anonymous viewers.
  // - isClaimed is true whenever the build has any owner (including the
  //   current user). Disables Save for non-owners since the API would
  //   return 409 anyway — surfacing that state up-front is cleaner UX.
  const { userId: clerkId } = await auth();
  let currentUserOwns = false;
  if (clerkId && build.userId !== null) {
    const [u] = await db
      .select({ id: users.id })
      .from(users)
      .where(eq(users.clerkId, clerkId))
      .limit(1);
    currentUserOwns = !!u && u.id === build.userId;
  }
  const isClaimed = build.userId !== null;

  const groups = await listCategoriesGrouped();

  // For each part in the build, compute its compat status against the build's vehicle.
  // N queries (one per item) — acceptable for ≤50 items per build.
  const compatByPart: Record<number, { status: CompatStatus; caveat: string | null }> = {};
  for (const it of build.items) {
    const ranked = await listCategoryPartsRankedForVehicle({
      categorySlug: it.part.categorySlug,
      vehicleId: build.vehicle.id,
    });
    const found = ranked.find((p) => p.id === it.part.id);
    if (found) compatByPart[it.part.id] = { status: found.status, caveat: found.caveat };
  }

  // Bucket items by category so each row only shows the part for its slot.
  const itemsByCategory = new Map<string, (typeof build.items)[number]>();
  for (const it of build.items) itemsByCategory.set(it.part.categorySlug, it);

  return (
    <>
      <SiteHeader crumbs={[{ label: 'build', href: '/parts' }, { label: slug }]} />
      <main className="mx-auto max-w-[1400px] px-6 py-12 flex-1">
        <p className="eyebrow-signal mb-3">[BUILD] · {slug}</p>
        <h1 className="display-lg">
          {build.vehicle.year} {build.vehicle.make} {build.vehicle.model}
          {build.vehicle.subModel ? ' ' + build.vehicle.subModel : ''}
          <span className="text-signal">.</span>
        </h1>
        <p className="body-sm mt-2">
          {build.vehicle.trim ? build.vehicle.trim + ' · ' : ''}
          {build.vehicle.generation} chassis
        </p>

        <div className="mt-10 grid grid-cols-12 gap-8">
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-3">
            {groups.map((g) => {
              // Group is open by default if the user has already added a part
              // in any of its leaves — keeps relevant rows visible without
              // forcing them to click. Empty groups stay collapsed so the
              // list isn't a wall.
              const filledInGroup = g.leaves.filter((l) => itemsByCategory.has(l.slug)).length;
              const defaultOpen = filledInGroup > 0;
              return (
                <details
                  key={g.parentSlug}
                  open={defaultOpen}
                  className="hairline group"
                >
                  <summary className="px-4 py-3 hairline-b flex items-center justify-between cursor-pointer hover:bg-surface select-none list-none">
                    <span className="display-md text-base text-fg">{g.parentName}</span>
                    <span className="text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-fg-muted tabular">
                      {filledInGroup} / {g.leaves.length} filled
                      <span className="ml-3 text-fg-dim group-open:hidden">▸</span>
                      <span className="ml-3 text-fg-dim hidden group-open:inline">▾</span>
                    </span>
                  </summary>
                  <ul>
                    {g.leaves.map((c) => {
                      const it = itemsByCategory.get(c.slug);
                      const itemWithCompat = it
                        ? {
                            ...it,
                            compatStatus: compatByPart[it.part.id]?.status ?? ('unknown' as CompatStatus),
                            compatCaveat: compatByPart[it.part.id]?.caveat ?? null,
                          }
                        : null;
                      return (
                        <BuildRow
                          key={c.slug}
                          buildSlug={slug}
                          vehicleId={build.vehicle.id}
                          categorySlug={c.slug}
                          categoryLabel={c.name}
                          item={itemWithCompat}
                        />
                      );
                    })}
                  </ul>
                </details>
              );
            })}
          </div>
          <aside className="col-span-12 lg:col-span-4">
            <BuildSummary build={build} />
          </aside>
        </div>

        <BuildActions
          buildSlug={slug}
          currentUserOwns={currentUserOwns}
          isClaimed={isClaimed}
        />
      </main>
      <SiteFooter />
    </>
  );
}
