import Link from "next/link";
import { notFound } from "next/navigation";
import {
  listPartsByCategory,
  listCategoriesWithCounts,
} from "@/lib/queries/parts";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";
import { partSlug, formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  const [rows, categories] = await Promise.all([
    listPartsByCategory(category),
    listCategoriesWithCounts(),
  ]);

  // even with 0 rows, render the page if the category slug is real (so users get a meaningful empty state)
  const known = categories.find((c) => c.slug === category);
  if (!known) return notFound();

  return (
    <>
      <SiteHeader
        crumbs={[
          { label: "catalog", href: "/parts" },
          { label: known.name.toLowerCase() },
        ]}
        liveCount={[
          { label: "MATCHES", value: rows.length },
          { label: "CAT", value: category.toUpperCase() },
        ]}
      />

      <main className="flex-1">
        {/* page header */}
        <section className="hairline-b">
          <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-10 grid grid-cols-12 gap-8 items-end">
            <div className="col-span-12 md:col-span-7">
              <p className="eyebrow-signal mb-4">[CAT/{category.toUpperCase()}]</p>
              <h1 className="display-lg">
                {known.name}
                <span className="text-signal">.</span>
              </h1>
              <p className="body-sm mt-3 max-w-xl">
                {rows.length === 0
                  ? `No ${known.name.toLowerCase()} parts indexed yet. Catalog grows as scrapers run.`
                  : `${rows.length} ${known.name.toLowerCase()} part${rows.length === 1 ? "" : "s"} compatible across ${rows.length === 0 ? 0 : "the"} platform list.`}
              </p>
            </div>
            <div className="col-span-12 md:col-span-5">
              <CategoryNeighbors current={category} categories={categories} />
            </div>
          </div>
        </section>

        {/* table header */}
        <section className="mx-auto max-w-[1400px] px-6">
          <div className="hairline-b py-3 grid grid-cols-12 gap-4 eyebrow text-[10px]">
            <span className="col-span-1">IDX</span>
            <span className="col-span-4">Brand / Model</span>
            <span className="col-span-4 hidden md:block">Description</span>
            <span className="col-span-2 text-right">Cheapest</span>
            <span className="col-span-1 text-right">×</span>
          </div>

          {rows.length === 0 ? (
            <EmptyCategory category={known.name} />
          ) : (
            <ul>
              {rows.map((p, i) => (
                <li key={p.id}>
                  <Link
                    href={`/part/${partSlug(p.brand)}/${partSlug(p.model)}`}
                    className="row-hover hairline-soft-b py-4 grid grid-cols-12 gap-4 items-baseline"
                  >
                    <span className="col-span-1 index-marker tabular">
                      {String(i + 1).padStart(3, "0")}
                    </span>
                    <span className="col-span-4 min-w-0">
                      <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                        {p.brand}
                      </span>
                      <span className="display-md text-base text-fg leading-tight truncate block">
                        {p.model}
                      </span>
                    </span>
                    <span className="col-span-4 hidden md:block body-sm text-fg-muted truncate">
                      {p.name}
                    </span>
                    <span className="col-span-2 figure text-fg text-right">
                      {formatPrice(p.cheapestPriceCents)}
                    </span>
                    <span className="col-span-1 figure text-right text-fg-muted text-sm">
                      ×{p.vendorCount}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

function CategoryNeighbors({
  current,
  categories,
}: {
  current: string;
  categories: { slug: string; name: string; partCount: number }[];
}) {
  const idx = categories.findIndex((c) => c.slug === current);
  const prev = categories[idx - 1];
  const next = categories[idx + 1];
  return (
    <div className="grid grid-cols-2 gap-px bg-line hairline">
      {prev ? (
        <Link href={`/parts/${prev.slug}`} className="bg-bg p-4 row-hover block">
          <p className="eyebrow text-[10px]">← Prev category</p>
          <p className="display-md text-fg text-base mt-2">{prev.name}</p>
          <p className="text-[10px] tracking-[0.1em] uppercase text-fg-dim font-[family-name:var(--font-mono)] mt-1">
            {prev.partCount} parts
          </p>
        </Link>
      ) : (
        <Link href="/parts" className="bg-bg p-4 row-hover block">
          <p className="eyebrow text-[10px]">← All</p>
          <p className="display-md text-fg text-base mt-2">Full catalog</p>
        </Link>
      )}
      {next ? (
        <Link href={`/parts/${next.slug}`} className="bg-bg p-4 row-hover block text-right">
          <p className="eyebrow text-[10px]">Next category →</p>
          <p className="display-md text-fg text-base mt-2">{next.name}</p>
          <p className="text-[10px] tracking-[0.1em] uppercase text-fg-dim font-[family-name:var(--font-mono)] mt-1">
            {next.partCount} parts
          </p>
        </Link>
      ) : (
        <Link href="/parts" className="bg-bg p-4 row-hover block text-right">
          <p className="eyebrow text-[10px]">All →</p>
          <p className="display-md text-fg text-base mt-2">Full catalog</p>
        </Link>
      )}
    </div>
  );
}

function EmptyCategory({ category }: { category: string }) {
  return (
    <div className="py-24 text-center">
      <p className="eyebrow mb-3">[NO MATCHES]</p>
      <p className="display-md mb-2">{category} catalog is empty</p>
      <p className="body-sm max-w-md mx-auto">
        Either no scraper has populated this category yet, or no vendor in the
        current scrape set carries this part type. Check back after Phase 2 vendor
        expansion.
      </p>
      <Link href="/parts" className="arrow-link mt-6 inline-flex">
        Back to full catalog
      </Link>
    </div>
  );
}
