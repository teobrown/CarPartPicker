// Vitest global setup: load .env.local before any test imports modules
// that read DATABASE_URL (e.g. lib/db/client.ts).
import { config } from 'dotenv';

config({ path: '.env.local' });
