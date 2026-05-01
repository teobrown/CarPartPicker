// Vitest per-worker setup: runs in every test worker BEFORE any test file
// imports modules that read DATABASE_URL (e.g. lib/db/client.ts).
//
// We must validate and override env in each worker because globalSetup runs
// in a separate process and its env vars don't propagate to test workers.
import { config } from 'dotenv';
import { resolve } from 'node:path';

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

// Override DATABASE_URL for the test run so all imports of lib/db/client see the test URL.
process.env.DATABASE_URL = testUrl;
