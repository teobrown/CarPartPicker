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
  const { sql, like, not } = await import('drizzle-orm');
  const { runCategorySeed } = await import('@/lib/db/seed/categories');

  const before = await db.select().from(categories);
  console.log(`existing categories before: ${before.length}`);

  // Idempotency / state-machine guard: detect which mode we're in by checking
  // the presence of two unambiguous sentinels — one only ever in the new
  // taxonomy, one only ever in the old. This is robust to manually-inserted
  // stray rows that happen to have a parent_id, which the prior parent_id-
  // based check would have been fooled by.
  const slugs = new Set(before.map((c) => c.slug));
  const hasNewSentinel = slugs.has('cold-air-intake'); // a leaf only in the new seed
  const hasOldSentinel = slugs.has('intake') && !slugs.has('intake-old'); // an old leaf, not yet suffixed
  const hasOldSuffixed = slugs.has('intake-old'); // an old leaf, already suffixed

  if (hasNewSentinel && (hasOldSentinel === false) && hasOldSuffixed === false) {
    // Already fully migrated AND old rows were already cleaned up (post-0007).
    console.log('migration already complete (new taxonomy present, old rows gone) — skipping suffix step');
  } else if (hasNewSentinel && hasOldSuffixed) {
    // Mid-flight: new taxonomy seeded, old rows still suffixed waiting on cleanup.
    console.log('new taxonomy already in place — skipping suffix step');
  } else if (hasOldSentinel && !hasNewSentinel) {
    // Fresh state: only the old taxonomy is here. Suffix it.
    await db
      .update(categories)
      .set({ slug: sql`${categories.slug} || '-old'` })
      .where(not(like(categories.slug, '%-old')));
    const suffixed = await db.select().from(categories);
    console.log(`after suffix pass: ${suffixed.length} rows, ${suffixed.filter((c) => c.slug.endsWith('-old')).length} now end in -old`);
  } else {
    // Mixed/unknown state — refuse to mutate. Fail closed.
    throw new Error(
      `categories table in an unexpected state: hasNewSentinel=${hasNewSentinel} ` +
        `hasOldSentinel=${hasOldSentinel} hasOldSuffixed=${hasOldSuffixed}. ` +
        `Inspect manually before running this script.`,
    );
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
