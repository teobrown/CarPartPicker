import { config } from 'dotenv';

// Next.js convention puts secrets in .env.local; load explicitly
// because tsx doesn't auto-load it.
config({ path: '.env.local' });

async function main() {
  // Registry pattern: adding a new seed is a one-line edit. Imports are
  // lazy so dotenv has loaded before lib/db/client.ts initializes the
  // postgres connection pool.
  const seeds = [
    { name: 'vehicles', run: () => import('./vehicles').then((m) => m.runVehicleSeed()) },
    // categories + vendors will be added in subsequent commits
  ];
  for (const s of seeds) {
    const n = await s.run();
    console.log(`${s.name} seeded: ${n}`);
  }
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
