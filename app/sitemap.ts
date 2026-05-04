import type { MetadataRoute } from "next";
import { listCategoriesWithCounts, listAllParts } from "@/lib/queries/parts";
import { partSlug } from "@/lib/format";

// Generate on request, not at build. The catalog grows with every scrape;
// baking the sitemap into the bundle would freeze it until the next deploy.
// Also guards against build-time DB unavailability — Vercel's build runner
// has no route to the prod Postgres, so a static sitemap.xml would block
// every deploy on a working DATABASE_URL when really we just want fresh
// catalog URLs on each crawler hit.
export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const baseEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/parts`, changeFrequency: "daily", priority: 0.9 },
  ];
  // Fail-soft on DB outage: a transient blip should serve the static
  // hub URLs rather than 500 the whole sitemap and tank crawl coverage.
  try {
    const [categories, allParts] = await Promise.all([
      listCategoriesWithCounts(),
      listAllParts(),
    ]);
    return [
      ...baseEntries,
      ...categories.map((c) => ({
        url: `${base}/parts/${c.slug}`,
        changeFrequency: "weekly" as const,
        priority: 0.7,
      })),
      ...allParts.map((p) => ({
        url: `${base}/part/${partSlug(p.brand)}/${partSlug(p.model)}`,
        changeFrequency: "weekly" as const,
        priority: 0.6,
      })),
    ];
  } catch (e) {
    console.error("[sitemap] db query failed, returning static hub URLs", e);
    return baseEntries;
  }
}
