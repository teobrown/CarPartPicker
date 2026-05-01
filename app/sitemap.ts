import type { MetadataRoute } from "next";
import { listCategoriesWithCounts, listAllParts } from "@/lib/queries/parts";
import { partSlug } from "@/lib/format";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const [categories, allParts] = await Promise.all([
    listCategoriesWithCounts(),
    listAllParts(),
  ]);
  return [
    { url: `${base}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/parts`, changeFrequency: "daily", priority: 0.9 },
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
}
