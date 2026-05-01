import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'node',
    // globalSetup: validates TEST_DATABASE_URL and runs migrations once per session.
    // setupFiles: re-validates and overrides DATABASE_URL inside each worker
    // (globalSetup's env mutations don't propagate to workers).
    globalSetup: ['./tests/setup-global.ts'],
    setupFiles: ['./tests/setup.ts'],
    // Force serial test-file execution: seed.test.ts and parts.queries.test.ts
    // both truncate seed-owned tables in their own beforeAll hooks. Running
    // them concurrently against the same Neon DB would race.
    fileParallelism: false,
    // Playwright owns tests/e2e/ — keep vitest from picking up *.spec.ts there.
    exclude: ['**/node_modules/**', '**/tests/e2e/**'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
