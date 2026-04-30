import { listPartsByCategory } from '@/lib/queries/parts';
import { notFound } from 'next/navigation';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default async function CategoryPage(
  { params }: { params: Promise<{ category: string }> },
) {
  const { category } = await params;
  const rows = await listPartsByCategory(category);
  if (rows.length === 0) return notFound();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold capitalize">{category.replace(/-/g, ' ')}</h1>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {rows.map((p) => (
          <li key={p.id} className="border rounded p-4">
            <Link href={`/part/${slugify(p.brand)}/${slugify(p.model)}`}>
              <h2 className="font-semibold">{p.brand} {p.model}</h2>
              <p className="mt-2 font-mono">
                {p.cheapestPriceCents !== null
                  ? `$${(p.cheapestPriceCents / 100).toFixed(2)}`
                  : 'No price'}
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
