'use server';

import { revalidatePath } from 'next/cache';
import { addBuildItem, removeBuildItem } from '@/lib/queries/builds';

export async function addItemAction({ slug, partId }: { slug: string; partId: number }) {
  await addBuildItem({ buildSlug: slug, partId });
  revalidatePath(`/build/${slug}`);
}

export async function removeItemAction({ slug, partId }: { slug: string; partId: number }) {
  await removeBuildItem({ buildSlug: slug, partId });
  revalidatePath(`/build/${slug}`);
}
