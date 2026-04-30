import { config } from 'dotenv';
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

// Next.js convention puts secrets in .env.local; load explicitly
// because tsx doesn't auto-load it.
config({ path: '.env.local' });

async function main() {
  const client = postgres(process.env.DATABASE_URL!, { max: 1 });
  const db = drizzle(client);
  await migrate(db, { migrationsFolder: './drizzle' });
  await client.end();
  console.log('migrations applied');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
