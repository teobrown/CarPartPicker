import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  test: {
    environment: 'node',
    setupFiles: ['./tests/setup.ts'],
    // Force serial test-file execution: seed.test.ts and parts.queries.test.ts
    // both truncate seed-owned tables in their own beforeAll hooks. Running
    // them concurrently against the same Neon DB would race.
    fileParallelism: false,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
