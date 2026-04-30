import { db } from '@/lib/db/client';
import { categories } from '@/lib/db/schema';

type C = typeof categories.$inferInsert;

const data: C[] = [
  { name: 'Intake', slug: 'intake' },
  { name: 'Catback Exhaust', slug: 'catback' },
  { name: 'Axleback Exhaust', slug: 'axleback' },
  { name: 'Muffler Delete', slug: 'muffler-delete' },
  { name: 'Tune', slug: 'tune' },
  { name: 'Downpipe', slug: 'downpipe' },
  { name: 'Intercooler', slug: 'intercooler' },
  { name: 'Blow-Off Valve', slug: 'bov' },
  { name: 'Coilovers', slug: 'coilovers' },
  { name: 'Lowering Springs', slug: 'springs' },
  { name: 'Sway Bars', slug: 'sway-bars' },
  { name: 'Wheels', slug: 'wheels' },
  { name: 'Tires', slug: 'tires' },
  { name: 'Lip Kit', slug: 'lip-kit' },
  { name: 'Spoiler', slug: 'spoiler' },
  { name: 'Fender Flares', slug: 'fender-flares' },
  { name: 'Headlights', slug: 'headlights' },
  { name: 'Taillights', slug: 'taillights' },
];

export async function runCategorySeed() {
  await db.insert(categories).values(data).onConflictDoNothing();
  return data.length;
}
