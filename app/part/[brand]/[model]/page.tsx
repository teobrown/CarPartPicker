import { getPartByBrandModel } from '@/lib/queries/parts';
import { notFound } from 'next/navigation';

export const dynamic = 'force-dynamic';

export default async function PartDetail(
  { params }: { params: Promise<{ brand: string; model: string }> },
) {
  const { brand, model } = await params;
  const p = await getPartByBrandModel(brand, model);
  if (!p) return notFound();
  return (
    <main className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold">{p.brand} {p.model}</h1>
      <p className="text-sm opacity-70 mb-4">{p.categorySlug}</p>
      {p.description && <p className="mb-6">{p.description}</p>}
      <h2 className="font-semibold mb-2">Vendors</h2>
      <ul className="space-y-2">
        {p.listings.map((l) => (
          <li key={l.listingId} className="border rounded p-3 flex justify-between">
            <span>{l.vendorName} {l.inStock ? '· in stock' : '· out of stock'}</span>
            <span className="font-mono">
              {l.priceCents !== null ? `$${(l.priceCents / 100).toFixed(2)}` : 'No price'}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}
