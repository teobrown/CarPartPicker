import Link from "next/link";
import { notFound } from "next/navigation";
import { getPartByBrandModel } from "@/lib/queries/parts";
import { SiteHeader } from "@/app/components/site-header";
import { SiteFooter } from "@/app/components/site-footer";
import { formatPrice } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function PartDetail({
  params,
}: {
  params: Promise<{ brand: string; model: string }>;
}) {
  const { brand, model } = await params;
  const p = await getPartByBrandModel(brand, model);
  if (!p) return notFound();

  const cheapest = p.cheapestPriceCents;
  const sortedListings = [...p.listings].sort((a, b) => {
    if (a.priceCents == null) return 1;
    if (b.priceCents == null) return -1;
    return a.priceCents - b.priceCents;
  });

  return (
    <>
      <SiteHeader
        crumbs={[
          { label: "catalog", href: "/parts" },
          { label: p.categorySlug, href: `/parts/${p.categorySlug}` },
          { label: p.model.toLowerCase() },
        ]}
        liveCount={[
          { label: "VENDORS", value: p.vendorCount },
          { label: "MIN", value: formatPrice(cheapest) },
        ]}
      />

      <main className="flex-1">
        {/* hero / spec sheet header */}
        <section className="hairline-b">
          <div className="mx-auto max-w-[1400px] px-6 pt-12 pb-12 grid grid-cols-12 gap-8">
            <div className="col-span-12 md:col-span-8">
              <p className="eyebrow-signal mb-4" data-reveal="0">
                [PART] · {p.categorySlug.toUpperCase()}
              </p>
              <p
                className="text-[12px] tracking-[0.16em] uppercase font-[family-name:var(--font-mono)] text-fg-muted mb-2"
                data-reveal="1"
              >
                {p.brand}
              </p>
              <h1 className="display-xl text-[clamp(2.25rem,5.5vw,4.25rem)] leading-[1.02]" data-reveal="2">
                {p.model}
                <span className="text-signal">.</span>
              </h1>
              <p className="body-sm mt-4 max-w-2xl" data-reveal="3">
                {p.description ?? p.name}
              </p>

              <div className="mt-10 flex flex-wrap items-center gap-4" data-reveal="4">
                {sortedListings[0] && (
                  <a
                    href={sortedListings[0].vendorUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary"
                  >
                    BUY @ {sortedListings[0].vendorName.toUpperCase()} ·{" "}
                    {formatPrice(sortedListings[0].priceCents)}
                  </a>
                )}
                <Link href={`/parts/${p.categorySlug}`} className="arrow-link">
                  Back to {p.categorySlug}
                </Link>
              </div>
            </div>

            {/* spec sheet sidebar */}
            <aside className="col-span-12 md:col-span-4" data-reveal="5">
              <div className="bracket-frame hairline bg-surface p-5">
                <p className="eyebrow-signal text-[10px] mb-4">SPEC SHEET</p>
                <dl className="space-y-3 text-[12px] font-[family-name:var(--font-mono)]">
                  <SpecRow label="BRAND" value={p.brand} />
                  <SpecRow label="MODEL" value={p.model} />
                  <SpecRow label="CATEGORY" value={p.categorySlug} />
                  <SpecRow label="VENDORS" value={`×${p.vendorCount}`} />
                  <SpecRow
                    label="CHEAPEST"
                    value={formatPrice(cheapest)}
                    highlight
                  />
                </dl>
              </div>
            </aside>
          </div>
        </section>

        {/* vendor matrix */}
        <section className="mx-auto max-w-[1400px] px-6 py-16">
          <div className="flex items-end justify-between mb-8 gap-6">
            <div>
              <p className="eyebrow mb-3">[VEN] · Vendor matrix</p>
              <h2 className="display-lg">{p.vendorCount} vendor{p.vendorCount === 1 ? "" : "s"}</h2>
            </div>
            <p className="body-sm hidden md:block max-w-md">
              Sorted by price, cheapest first. Click any row to open the vendor
              page in a new tab.
              <span className="block mt-1 text-fg-dim">
                Phase 1 routes the click through <span className="text-fg font-[family-name:var(--font-mono)]">/go/[id]</span> with the affiliate code attached.
              </span>
            </p>
          </div>

          <div className="hairline">
            {/* header */}
            <div className="hairline-b py-3 px-5 grid grid-cols-12 gap-4 eyebrow text-[10px] bg-bg-deep">
              <span className="col-span-1">RANK</span>
              <span className="col-span-4">Vendor</span>
              <span className="col-span-3 hidden md:block">Status</span>
              <span className="col-span-3 md:col-span-2 text-right">Price</span>
              <span className="col-span-4 md:col-span-2 text-right">Action</span>
            </div>

            {sortedListings.length === 0 ? (
              <div className="py-16 text-center">
                <p className="eyebrow mb-3">[NO LISTINGS]</p>
                <p className="body-sm">No vendor listings for this part yet.</p>
              </div>
            ) : (
              <ul>
                {sortedListings.map((l, i) => {
                  const isCheapest = i === 0 && l.priceCents != null;
                  return (
                    <li key={l.listingId} className="hairline-soft-b last:border-b-0">
                      <a
                        href={l.vendorUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="row-hover py-4 px-5 grid grid-cols-12 gap-4 items-center"
                      >
                        <span className="col-span-1 index-marker tabular">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="col-span-4 min-w-0">
                          <span className="display-md text-base text-fg leading-tight truncate block">
                            {l.vendorName}
                          </span>
                          <span className="text-[10px] tracking-[0.1em] uppercase text-fg-dim font-[family-name:var(--font-mono)]">
                            /{l.vendorSlug}
                          </span>
                        </span>
                        <span className="col-span-3 hidden md:flex items-center gap-2 text-[11px] tracking-[0.08em] uppercase font-[family-name:var(--font-mono)]">
                          {l.inStock ? (
                            <>
                              <span className="pip" />
                              <span className="text-fg">In stock</span>
                            </>
                          ) : (
                            <>
                              <span className="pip pip-red" />
                              <span className="text-fg-dim">Out of stock</span>
                            </>
                          )}
                        </span>
                        <span className="col-span-3 md:col-span-2 text-right">
                          <span
                            className={
                              "figure text-base block " +
                              (isCheapest ? "text-signal" : "text-fg")
                            }
                          >
                            {formatPrice(l.priceCents)}
                          </span>
                          {isCheapest && (
                            <span className="eyebrow-signal text-[9px]">CHEAPEST</span>
                          )}
                        </span>
                        <span className="col-span-4 md:col-span-2 text-right">
                          <span className="arrow-link justify-end">View</span>
                        </span>
                      </a>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        {/* compatibility placeholder */}
        <section className="hairline-t bg-bg-deep">
          <div className="mx-auto max-w-[1400px] px-6 py-16">
            <p className="eyebrow mb-3">[FIT] · Compatibility</p>
            <h2 className="display-lg max-w-3xl">
              <span className="text-fg-muted">Compatibility engine ships in </span>
              <span className="text-fg">Phase 1</span>
              <span className="text-signal">.</span>
            </h2>
            <p className="body-sm mt-4 max-w-2xl">
              The Phase 0 catalog stores vendor-claimed fitment per part. The build
              editor and live compat checks (green ✓ / yellow ⚠ caveat / red ❌
              incompatible) ride on top of those rules in Phase 1, keyed off your
              selected vehicle.
            </p>

            <div className="mt-10 grid gap-px bg-line hairline grid-cols-1 md:grid-cols-3">
              <CompatCard
                state="ok"
                title="Compatibility lookup"
                detail="SQL window query · ranks rules by status priority per vehicle"
              />
              <CompatCard
                state="next"
                title="Wheel/tire geometric fit"
                detail="pure-function calculator · poke / rub thresholds from real spec sheets"
              />
              <CompatCard
                state="next"
                title="Cross-part rules"
                detail="downpipe requires tune · catback conflicts with axleback · client-side"
              />
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}

function SpecRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 hairline-soft-b pb-2 last:border-b-0 last:pb-0">
      <dt className="text-fg-dim tracking-[0.1em] text-[10px] uppercase">{label}</dt>
      <dd
        className={
          "tabular text-right truncate " +
          (highlight ? "text-signal" : "text-fg")
        }
      >
        {value}
      </dd>
    </div>
  );
}

function CompatCard({
  state,
  title,
  detail,
}: {
  state: "ok" | "next" | "later";
  title: string;
  detail: string;
}) {
  const meta = {
    ok: { pip: "pip", label: "READY" },
    next: { pip: "pip pip-amber", label: "PHASE 1" },
    later: { pip: "pip pip-dim", label: "LATER" },
  }[state];
  return (
    <div className="bg-bg-deep p-5">
      <div className="flex items-center justify-between mb-4">
        <span className={meta.pip} />
        <span className="text-[10px] tracking-[0.14em] uppercase font-[family-name:var(--font-mono)] text-fg-dim">
          {meta.label}
        </span>
      </div>
      <p className="display-md text-fg text-base leading-tight">{title}</p>
      <p className="text-[11px] mt-3 font-[family-name:var(--font-mono)] text-fg-muted leading-relaxed">
        {detail}
      </p>
    </div>
  );
}
