import { Webhook } from "svix";
import { headers } from "next/headers";
import type { WebhookEvent } from "@clerk/nextjs/server";
import { db } from "@/lib/db/client";
import { users } from "@/lib/db/schema";
import { eq } from "drizzle-orm";

// Clerk -> Carbuildr webhook. Configured in the Clerk dashboard
// (Webhooks -> Add Endpoint -> URL = https://www.carbuildr.com/api/webhooks/clerk).
// We listen for user lifecycle events to keep the local users mirror in sync:
//   user.created  -> insert (id, clerk_id, email)
//   user.updated  -> update email if it changed
//   user.deleted  -> delete user row (builds.user_id FK is ON DELETE SET NULL,
//                    so claimed builds become anonymous again rather than vanish)
//
// Signature verification via svix is non-negotiable — without it, anyone could
// POST a forged payload and create/delete users.

export async function POST(req: Request) {
  const secret = process.env.CLERK_WEBHOOK_SECRET;
  if (!secret) {
    console.error("[clerk webhook] CLERK_WEBHOOK_SECRET not configured");
    return new Response("server misconfigured", { status: 500 });
  }

  const h = await headers();
  const svixId = h.get("svix-id");
  const svixTimestamp = h.get("svix-timestamp");
  const svixSignature = h.get("svix-signature");
  if (!svixId || !svixTimestamp || !svixSignature) {
    return new Response("missing svix headers", { status: 400 });
  }

  const body = await req.text();

  let evt: WebhookEvent;
  try {
    evt = new Webhook(secret).verify(body, {
      "svix-id": svixId,
      "svix-timestamp": svixTimestamp,
      "svix-signature": svixSignature,
    }) as WebhookEvent;
  } catch (e) {
    console.warn("[clerk webhook] signature verify failed", e);
    return new Response("invalid signature", { status: 400 });
  }

  const type = evt.type;
  if (type === "user.created" || type === "user.updated") {
    const u = evt.data;
    const primaryEmail =
      u.email_addresses?.find((e) => e.id === u.primary_email_address_id)
        ?.email_address ?? u.email_addresses?.[0]?.email_address ?? null;
    await db
      .insert(users)
      .values({ clerkId: u.id, email: primaryEmail })
      .onConflictDoUpdate({
        target: users.clerkId,
        set: { email: primaryEmail },
      });
  } else if (type === "user.deleted") {
    const id = evt.data.id;
    if (id) {
      await db.delete(users).where(eq(users.clerkId, id));
    }
  }
  return new Response("ok", { status: 200 });
}
