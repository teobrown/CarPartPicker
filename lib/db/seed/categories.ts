import { db } from '@/lib/db/client';
import { categories } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

type CRow = typeof categories.$inferInsert;

// Parent groups, in stable display order. The order also fixes which parent
// `id` lands first — leaf rows resolve their `parent_id` by looking up the
// parent's slug after the parent insert.
const PARENTS: Array<{ name: string; slug: string; hiddenFromPicker?: boolean }> = [
  { name: 'Intake',           slug: 'intake' },
  { name: 'Exhaust',          slug: 'exhaust' },
  { name: 'Forced Induction', slug: 'forced-induction' },
  { name: 'Tuning',           slug: 'tuning' },
  { name: 'Suspension',       slug: 'suspension' },
  { name: 'Wheels & Tires',   slug: 'wheels-tires' },
  { name: 'Brakes',           slug: 'brakes' },
  { name: 'Body & Aero',      slug: 'body-aero' },
  { name: 'Lighting',         slug: 'lighting' },
  { name: 'Internal',         slug: 'internal',         hiddenFromPicker: true },
];

// Leaves keyed by parent slug. The `hidden` flag promotes to `hidden_from_picker`.
const LEAVES: Array<{ parent: string; name: string; slug: string; hidden?: boolean }> = [
  // Intake
  { parent: 'intake', name: 'Cold Air Intake',    slug: 'cold-air-intake' },
  { parent: 'intake', name: 'Short Ram Intake',   slug: 'short-ram-intake' },
  { parent: 'intake', name: 'Ram Air Intake',     slug: 'ram-air-intake' },
  { parent: 'intake', name: 'Intake Manifold',    slug: 'intake-manifold' },
  { parent: 'intake', name: 'Air Filter',         slug: 'air-filter' },
  { parent: 'intake', name: 'Intake Hose',        slug: 'intake-hose' },
  { parent: 'intake', name: 'MAF Housing',        slug: 'maf-housing' },

  // Exhaust
  { parent: 'exhaust', name: 'Catback Exhaust',     slug: 'catback-exhaust' },
  { parent: 'exhaust', name: 'Axleback Exhaust',    slug: 'axleback-exhaust' },
  { parent: 'exhaust', name: 'Front Pipe',          slug: 'front-pipe' },
  { parent: 'exhaust', name: 'Downpipe',            slug: 'downpipe' },
  { parent: 'exhaust', name: 'Muffler Delete',      slug: 'muffler-delete' },
  { parent: 'exhaust', name: 'Exhaust Tip',         slug: 'exhaust-tip' },
  { parent: 'exhaust', name: 'O2 Sensor',           slug: 'o2-sensor' },
  { parent: 'exhaust', name: 'Exhaust Hardware',    slug: 'exhaust-hardware' },

  // Forced Induction
  { parent: 'forced-induction', name: 'Intercooler',  slug: 'intercooler' },
  { parent: 'forced-induction', name: 'Charge Pipe',  slug: 'charge-pipe' },
  { parent: 'forced-induction', name: 'Blow-Off Valve', slug: 'bov' },
  { parent: 'forced-induction', name: 'Wastegate',    slug: 'wastegate' },

  // Tuning
  { parent: 'tuning', name: 'ECU Tune',         slug: 'ecu-tune' },
  { parent: 'tuning', name: 'Wideband / Gauge', slug: 'wideband-gauge' },

  // Suspension
  { parent: 'suspension', name: 'Coilovers',         slug: 'coilovers' },
  { parent: 'suspension', name: 'Lowering Springs',  slug: 'lowering-springs' },
  { parent: 'suspension', name: 'Sway Bars',         slug: 'sway-bars' },
  { parent: 'suspension', name: 'End Links',         slug: 'end-links' },
  { parent: 'suspension', name: 'Control Arms',      slug: 'control-arms' },
  { parent: 'suspension', name: 'Strut Bar',         slug: 'strut-bar' },
  { parent: 'suspension', name: 'Camber Kit',        slug: 'camber-kit' },
  { parent: 'suspension', name: 'Bushings',          slug: 'bushings' },

  // Wheels & Tires
  { parent: 'wheels-tires', name: 'Wheels',         slug: 'wheels' },
  { parent: 'wheels-tires', name: 'Tires',          slug: 'tires' },
  { parent: 'wheels-tires', name: 'Wheel Spacers',  slug: 'wheel-spacers' },
  { parent: 'wheels-tires', name: 'Lug Nuts & Studs', slug: 'lug-nuts-studs' },
  { parent: 'wheels-tires', name: 'Hub Centric Rings', slug: 'hub-rings' },

  // Brakes
  { parent: 'brakes', name: 'Brake Pads',     slug: 'brake-pads' },
  { parent: 'brakes', name: 'Brake Rotors',   slug: 'brake-rotors' },
  { parent: 'brakes', name: 'Brake Lines',    slug: 'brake-lines' },
  { parent: 'brakes', name: 'Big Brake Kit',  slug: 'big-brake-kit' },

  // Body & Aero
  { parent: 'body-aero', name: 'Front Lip',     slug: 'front-lip' },
  { parent: 'body-aero', name: 'Side Skirts',   slug: 'side-skirts' },
  { parent: 'body-aero', name: 'Rear Diffuser', slug: 'rear-diffuser' },
  { parent: 'body-aero', name: 'Spoiler / Wing', slug: 'spoiler-wing' },
  { parent: 'body-aero', name: 'Hood',          slug: 'hood' },
  { parent: 'body-aero', name: 'Fender Flares', slug: 'fender-flares' },

  // Lighting
  { parent: 'lighting', name: 'Headlights', slug: 'headlights' },
  { parent: 'lighting', name: 'Taillights', slug: 'taillights' },
  { parent: 'lighting', name: 'Fog Lights', slug: 'fog-lights' },
  { parent: 'lighting', name: 'LED Bulbs',  slug: 'led-bulbs' },

  // Internal (admin-only)
  { parent: 'internal', name: 'Misc', slug: 'misc', hidden: true },
];

export async function runCategorySeed(): Promise<number> {
  // Insert parents first so they exist for the leaf parent_id lookup.
  const parentRows: CRow[] = PARENTS.map((p) => ({
    name: p.name,
    slug: p.slug,
    hiddenFromPicker: p.hiddenFromPicker ?? false,
  }));
  await db.insert(categories).values(parentRows).onConflictDoNothing();

  // Resolve parent slug -> id once.
  const parentSlugToId = new Map<string, number>();
  for (const p of PARENTS) {
    const [row] = await db
      .select({ id: categories.id })
      .from(categories)
      .where(eq(categories.slug, p.slug))
      .limit(1);
    if (!row) throw new Error(`parent missing after insert: ${p.slug}`);
    parentSlugToId.set(p.slug, row.id);
  }

  const leafRows: CRow[] = LEAVES.map((l) => ({
    name: l.name,
    slug: l.slug,
    parentId: parentSlugToId.get(l.parent)!,
    hiddenFromPicker: l.hidden ?? false,
  }));
  await db.insert(categories).values(leafRows).onConflictDoNothing();

  return parentRows.length + leafRows.length;
}
