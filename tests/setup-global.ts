// Vitest globalSetup: runs once before any test files import anything.
// Responsibilities:
//   1. Load .env.local
//   2. Refuse to run if TEST_DATABASE_URL is unset or equal to DATABASE_URL.
//      Tests TRUNCATE tables; pointing them at a dev/prod DB is destructive.
//   3. Override DATABASE_URL with TEST_DATABASE_URL so all imports of
//      lib/db/client see the test URL.
//   4. Apply pending migrations to the test DB so a fresh test DB just works.
import { config } from 'dotenv';
import { resolve } from 'node:path';
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

export default async function globalSetup() {
  config({ path: resolve(__dirname, '..', '.env.local') });

  const testUrl = process.env.TEST_DATABASE_URL;
  const prodUrl = process.env.DATABASE_URL;

  if (!testUrl) {
    throw new Error(
      'TEST_DATABASE_URL is required to run tests. Set it in .env.local. ' +
        'It MUST point at a separate database from DATABASE_URL — tests truncate tables.',
    );
  }
  if (testUrl === prodUrl) {
    throw new Error(
      'TEST_DATABASE_URL must NOT equal DATABASE_URL. ' +
        'Tests truncate tables. Use a separate database for testing.',
    );
  }

  // NOTE: deliberately do NOT mutate process.env.DATABASE_URL here.
  // Vitest passes the parent process's env to its workers, which would defeat
  // the per-worker validation in tests/setup.ts (it would see DATABASE_URL
  // already equal to TEST_DATABASE_URL and the inequality check would fire
  // even when .env.local has a legitimately different DATABASE_URL).
  // The per-worker setup file handles the override.

  // Ensure the test DB has the latest schema. Runs once per test session.
  const migrationClient = postgres(testUrl, { max: 1 });
  try {
    await migrate(drizzle(migrationClient), { migrationsFolder: './drizzle' });
  } finally {
    await migrationClient.end();
  }
}
