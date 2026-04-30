import { listAllParts } from '@/lib/queries/parts';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function PartsCatalog() {
  const rows = await listAllParts();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Parts Catalog</h1>
      <p className="text-sm opacity-70 mb-6">{rows.length} parts</p>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {rows.map((p) => (
          <li key={p.id} className="border rounded p-4">
            <Link href={`/part/${slugify(p.brand)}/${slugify(p.model)}`}>
              <h2 className="font-semibold">{p.brand} {p.model}</h2>
              <p className="text-xs opacity-60">{p.categorySlug}</p>
              <p className="mt-2 font-mono">
                {p.cheapestPriceCents !== null
                  ? `$${(p.cheapestPriceCents / 100).toFixed(2)}`
                  : 'No price'}{' '}
                <span className="text-xs opacity-60">· {p.vendorCount} vendor(s)</span>
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
