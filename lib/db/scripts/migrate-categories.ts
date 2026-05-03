// One-shot data migration: suffix every existing category slug with '-old' so
// the rewritten seed can insert the new taxonomy without slug collisions.
// Then runs the seed. Existing parts.category_id values still point at the
// (now suffixed) old categories — the Python reclassifier moves them next.
//
// Idempotent: re-running on a DB that's already been migrated does nothing
// material (the `-old` suffix is only applied if the slug isn't already
// suffixed, and the seed uses ON CONFLICT DO NOTHING).
import { config } from 'dotenv';
config({ path: '.env.local' });

// Dynamic imports keep dotenv ahead of lib/db/client.ts — same pattern as
// lib/db/seed/run.ts. Static imports are hoisted and would initialize the
// postgres pool before config() runs, leaving DATABASE_URL undefined.
async function main() {
  console.log('--- migrate-categories ---');

  const { db } = await import('@/lib/db/client');
  const { categories } = await import('@/lib/db/schema');
  const { sql, like, not, isNotNull } = await import('drizzle-orm');
  const { runCategorySeed } = await import('@/lib/db/seed/categories');

  const before = await db.select().from(categories);
  console.log(`existing categories before: ${before.length}`);

  // Idempotency guard: if any row already has a parent_id, the new taxonomy
  // is in place and the suffix step has already run on a prior invocation.
  // Skip it — re-suffixing the new top-level slugs (intake, coilovers, etc.)
  // would collide with the -old rows already on disk.
  const newTaxonomyApplied = before.some((c) => c.parentId != null);
  if (newTaxonomyApplied) {
    console.log('new taxonomy already in place — skipping suffix step');
  } else {
    await db
      .update(categories)
      .set({ slug: sql`${categories.slug} || '-old'` })
      .where(not(like(categories.slug, '%-old')));
    const suffixed = await db.select().from(categories);
    console.log(`after suffix pass: ${suffixed.length} rows, ${suffixed.filter((c) => c.slug.endsWith('-old')).length} now end in -old`);
  }

  // Always run the seed — it's idempotent via ON CONFLICT DO NOTHING.
  const inserted = await runCategorySeed();
  console.log(`runCategorySeed reports ${inserted} rows attempted`);

  const after = await db.select().from(categories);
  const olds = after.filter((c) => c.slug.endsWith('-old'));
  const news = after.filter((c) => !c.slug.endsWith('-old'));
  console.log(`final: ${after.length} rows total — ${news.length} new + ${olds.length} old (-old)`);

  process.exit(0);
}
main().catch((err) => {
  console.error(err);
  process.exit(1);
});
