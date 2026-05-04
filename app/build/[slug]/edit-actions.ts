'use server';

import { revalidatePath } from 'next/cache';
import { auth } from '@clerk/nextjs/server';
import { addBuildItem, removeBuildItem } from '@/lib/queries/builds';

// Build mutations are gated by ownership: anyone can edit anonymous
// builds (user_id IS NULL), only the owner can edit claimed ones. We
// pull the actor's Clerk id here once and hand it to the mutator so
// the auth context doesn't leak into the data-layer module.

export async function addItemAction({ slug, partId }: { slug: string; partId: number }) {
  const { userId } = await auth();
  await addBuildItem({ buildSlug: slug, partId, actorClerkId: userId ?? null });
  revalidatePath(`/build/${slug}`);
}

export async function removeItemAction({ slug, partId }: { slug: string; partId: number }) {
  const { userId } = await auth();
  await removeBuildItem({ buildSlug: slug, partId, actorClerkId: userId ?? null });
  revalidatePath(`/build/${slug}`);
}
