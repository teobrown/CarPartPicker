-- Users table — local mirror of Clerk identities.
-- clerk_id is source of truth; email + created_at let us render UI
-- without round-tripping to Clerk on every render.
CREATE TABLE IF NOT EXISTS "users" (
    "id" serial PRIMARY KEY NOT NULL,
    "clerk_id" varchar(64) NOT NULL UNIQUE,
    "email" varchar(256),
    "created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint

-- Replace the unused builds.owner_user_id placeholder with a proper FK
-- to users.id. owner_user_id was never populated (default NULL on every
-- existing row), so we can drop it cleanly.
ALTER TABLE "builds" DROP COLUMN IF EXISTS "owner_user_id";
--> statement-breakpoint

ALTER TABLE "builds"
    ADD COLUMN "user_id" integer REFERENCES "users"("id") ON DELETE SET NULL;
--> statement-breakpoint

-- Index for /dashboard "show me my builds" lookups.
CREATE INDEX "builds_user_idx" ON "builds" ("user_id");
