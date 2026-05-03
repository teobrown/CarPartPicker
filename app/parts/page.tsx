import type { Metadata } from "next";
import Link from "next/link";
import {
  listAllParts,
  listCategoriesWithCounts,
  getCatalogStats,
} from "@/lib/queries/parts";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";
import { partSlug, formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const stats = await getCatalogStats();
  const description =
    stats.partCount === 0
      ? "Browse the Carbuildr parts registry. Catalog grows as scrapers run."
      : `${stats.partCount} parts indexed across ${stats.vendorCount} vendors. Filter by category or browse the full registry.`;
  return {
    title: "Catalog",
    description,
    openGraph: {
      title: "Catalog · Carbuildr",
      description,
      type: "website",
    },
  };
}

export default async function PartsCatalog() {
  const [rows, categories, stats] = await Promise.all([
    listAllParts(),
    listCategoriesWithCounts(),
    getCatalogStats(),
  ]);

  return (
    <>
      <SiteHeader
        crumbs={[{ label: "catalog" }]}
        liveCount={[
          { label: "PARTS", value: stats.partCount },
          { label: "LISTINGS", value: stats.listingCount },
        ]}
      />

      <main className="flex-1">
        {/* page header */}
        <section className="hairline-b">
          <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-10 grid grid-cols-12 gap-8 items-end">
            <div className="col-span-12 md:col-span-7">
              <p className="eyebrow-signal mb-4">[CAT] · Parts registry</p>
              <h1 className="display-lg">
                Catalog<span className="text-signal">.</span>
              </h1>
              <p className="body-sm mt-3 max-w-xl">
                {rows.length === 0
                  ? "No parts indexed yet. Run a scrape — see the README."
                  : `${rows.length} parts indexed across ${stats.vendorCount} vendors. Filter by category below or browse the full registry.`}
              </p>
            </div>
            <div className="col-span-12 md:col-span-5">
              <dl className="grid grid-cols-3 gap-px bg-line hairline">
                <DefBlock label="Parts" value={stats.partCount} />
                <DefBlock label="Listings" value={stats.listingCount} />
                <DefBlock label="Vendors" value={stats.vendorCount} />
              </dl>
            </div>
          </div>
        </section>

        {/* category filter chips */}
        <section className="hairline-b bg-bg-deep">
          <div className="mx-auto max-w-[1400px] px-6 py-4 flex items-center gap-3 overflow-x-auto">
            <span className="eyebrow shrink-0 mr-2">FILTER /</span>
            <CategoryChip href="/parts" label="ALL" count={rows.length} active />
            {categories.map((c) => (
              <CategoryChip
                key={c.slug}
                href={`/parts/${c.slug}`}
                label={c.name}
                count={c.partCount}
              />
            ))}
          </div>
        </section>

        {/* table header */}
        <section className="mx-auto max-w-[1400px] px-6">
          <div className="hairline-b py-3 grid grid-cols-12 gap-4 eyebrow text-[10px] sticky top-0 bg-bg z-10">
            <span className="col-span-1">IDX</span>
            <span className="col-span-3">Brand / Model</span>
            <span className="col-span-3 hidden md:block">Description</span>
            <span className="col-span-2">Category</span>
            <span className="col-span-2 text-right">Cheapest</span>
            <span className="col-span-1 text-right">Vendors</span>
          </div>

          {rows.length === 0 ? (
            <EmptyState />
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
                    <span className="col-span-3 min-w-0">
                      <span className="block text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
                        {p.brand}
                      </span>
                      <span className="display-md text-base text-fg leading-tight truncate block">
                        {p.model}
                      </span>
                    </span>
                    <span className="col-span-3 hidden md:block body-sm text-fg-muted truncate">
                      {p.name}
                    </span>
                    <span className="col-span-2 text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-fg-muted">
                      {p.categorySlug}
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

function DefBlock({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-bg p-4">
      <dt className="eyebrow text-[10px]">{label}</dt>
      <dd className="figure text-2xl text-fg mt-1">{value}</dd>
    </div>
  );
}

function CategoryChip({
  href,
  label,
  count,
  active,
}: {
  href: string;
  label: string;
  count: number;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      className={
        "shrink-0 px-3 py-1.5 hairline text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] transition-colors flex items-center gap-2 " +
        (active
          ? "border-signal text-signal"
          : "border-line text-fg-muted hover:text-fg hover:border-fg-muted")
      }
    >
      <span>{label}</span>
      <span className="text-fg-dim tabular">{count}</span>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="py-24 text-center">
      <p className="eyebrow mb-3">[NO DATA]</p>
      <p className="display-md mb-2">Catalog is empty</p>
      <p className="body-sm max-w-md mx-auto">
        Run the FCP Euro fixture import or the live scraper to populate the
        catalog. See <span className="font-[family-name:var(--font-mono)] text-fg">README.md</span> for commands.
      </p>
    </div>
  );
}
