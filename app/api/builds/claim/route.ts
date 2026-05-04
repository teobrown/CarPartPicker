import { auth } from "@clerk/nextjs/server";
import { db } from "@/lib/db/client";
import { builds, users } from "@/lib/db/schema";
import { eq, and, isNull } from "drizzle-orm";

// Claim an anonymous build to the current Clerk user.
//
// Contract:
//   - POST /api/builds/claim  body={"slug":"abcd1234"}
//   - 401 if not signed in
//   - 400 if slug missing or build doesn't exist
//   - 409 if build is already claimed (by anyone, including the same user
//         on a re-claim — already-yours is a no-op success but we 200 it)
//   - 200 {"ok":true,"slug":"abcd1234"} on success
//
// Atomicity: a single UPDATE ... WHERE user_id IS NULL guarantees no
// race where two concurrent claims both succeed. Postgres returns 0
// rows affected for the loser.

export async function POST(req: Request) {
  const { userId: clerkId } = await auth();
  if (!clerkId) return Response.json({ error: "not signed in" }, { status: 401 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid json" }, { status: 400 });
  }
  const slug =
    typeof body === "object" && body !== null && "slug" in body
      ? (body as { slug: unknown }).slug
      : null;
  if (typeof slug !== "string" || slug.length === 0) {
    return Response.json({ error: "slug required" }, { status: 400 });
  }

  // Look up the local user row. The Clerk webhook should have created
  // it on user.created; if it hasn't fired yet (race during signup),
  // upsert here so the user can claim immediately without a refresh.
  const [u] = await db
    .insert(users)
    .values({ clerkId })
    .onConflictDoUpdate({
      target: users.clerkId,
      set: { clerkId },  // no-op update so .returning() still fires
    })
    .returning({ id: users.id });

  // First, check if this user already owns the build — if so, return 200.
  const [existing] = await db
    .select({ id: builds.id, userId: builds.userId })
    .from(builds)
    .where(eq(builds.slug, slug))
    .limit(1);
  if (!existing) {
    return Response.json({ error: "build not found" }, { status: 400 });
  }
  if (existing.userId === u.id) {
    return Response.json({ ok: true, slug, alreadyYours: true });
  }
  if (existing.userId !== null) {
    return Response.json({ error: "build already claimed" }, { status: 409 });
  }

  // Atomic claim: update only if still anonymous.
  const result = await db
    .update(builds)
    .set({ userId: u.id, updatedAt: new Date() })
    .where(and(eq(builds.slug, slug), isNull(builds.userId)))
    .returning({ id: builds.id });

  if (result.length === 0) {
    // Lost the race — someone else just claimed it.
    return Response.json({ error: "build already claimed" }, { status: 409 });
  }
  return Response.json({ ok: true, slug });
}
