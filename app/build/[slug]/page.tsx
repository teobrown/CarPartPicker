import { notFound } from 'next/navigation';
import { getBuild } from '@/lib/queries/builds';
import { SiteHeader } from '@/app/components/site-header';
import { SiteFooter } from '@/app/components/site-footer';

export const dynamic = 'force-dynamic';

export default async function BuildPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const build = await getBuild(slug);
  if (!build) return notFound();
  return (
    <>
      <SiteHeader crumbs={[{ label: 'build', href: '/parts' }, { label: slug }]} />
      <main className="mx-auto max-w-[1400px] px-6 py-12 flex-1">
        <p className="eyebrow-signal mb-4">[BUILD] · {slug}</p>
        <h1 className="display-lg">
          {build.vehicle.year} {build.vehicle.make} {build.vehicle.model}
          {build.vehicle.subModel ? ' ' + build.vehicle.subModel : ''}
        </h1>
        <p className="body-sm mt-2">
          {build.vehicle.trim ? build.vehicle.trim + ' · ' : ''}
          {build.vehicle.generation} chassis · {build.items.length} parts in build
        </p>
        <p className="eyebrow mt-12 text-fg-dim">Build editor lands in Task 2.</p>
      </main>
      <SiteFooter />
    </>
  );
}
