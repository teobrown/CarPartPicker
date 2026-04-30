import { defineConfig } from 'drizzle-kit';
import { config } from 'dotenv';

// Next.js convention puts secrets in .env.local; load explicitly so
// drizzle-kit (run via tsx/node directly) can see DATABASE_URL.
config({ path: '.env.local' });

export default defineConfig({
  schema: './lib/db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: { url: process.env.DATABASE_URL! },
});
