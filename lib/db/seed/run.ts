import { config } from 'dotenv';

// Next.js convention puts secrets in .env.local; load explicitly
// because tsx doesn't auto-load it.
config({ path: '.env.local' });

async function main() {
  // Import after dotenv has loaded so DATABASE_URL is available when
  // lib/db/client.ts initializes the postgres connection pool.
  const { runVehicleSeed } = await import('./vehicles');
  const n = await runVehicleSeed();
  console.log(`vehicles seeded: ${n}`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
