'use client';

import { useState, useTransition } from 'react';
import { useAuth, SignInButton } from '@clerk/nextjs';

type Props = {
  buildSlug: string;
  // Server-resolved: does the current Clerk user own this build's row?
  // True only when the user is signed in AND builds.user_id matches their
  // local users.id. False for anonymous viewers, signed-in non-owners, and
  // owners-of-other-builds.
  currentUserOwns: boolean;
  // Build is claimed (by anyone) — disables Save for non-owners since the
  // claim endpoint will 409 anyway.
  isClaimed: boolean;
};

// Render the bottom-row actions on the build editor: Save Build + Share Build.
// Both are auth-gated. Signed-out users see SignInButton-wrapped buttons that
// open the Clerk modal; signing in does NOT auto-save — the build stays in
// place and the user re-clicks the action they want. This matches the
// product spec: "When a user signs in, it shouldn't be auto saved; however,
// it should still give them the option to save the build."
export function BuildActions({ buildSlug, currentUserOwns, isClaimed }: Props) {
  const [pending, startTransition] = useTransition();
  const [toast, setToast] = useState<string | null>(null);
  const { isSignedIn, isLoaded } = useAuth();

  function showToast(msg: string) {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2400);
  }

  async function copyShareLink() {
    const url = `${window.location.origin}/build/${buildSlug}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast('Link copied');
    } catch {
      showToast('Copy failed — copy from URL bar');
    }
  }

  async function claimBuild() {
    const res = await fetch('/api/builds/claim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: buildSlug }),
    });
    if (res.ok) {
      showToast('Build saved');
      // Reload so server props pick up the new ownership.
      window.location.reload();
    } else if (res.status === 409) {
      showToast('Already claimed by someone else');
    } else if (res.status === 401) {
      showToast('Sign in required');
    } else {
      showToast('Could not save');
    }
  }

  // Save Build button content varies by ownership state.
  let saveContent: React.ReactNode;
  if (currentUserOwns) {
    saveContent = (
      <button
        disabled
        className="btn-ghost py-2.5 px-4 opacity-70 cursor-default"
        title="Already saved to your account"
      >
        ✓ SAVED
      </button>
    );
  } else if (isClaimed) {
    // Build is claimed by someone else — Save is unavailable.
    saveContent = (
      <button
        disabled
        className="btn-ghost py-2.5 px-4 opacity-50 cursor-not-allowed"
        title="This build belongs to another user"
      >
        SAVE BUILD
      </button>
    );
  } else {
    // Anonymous build. Signed-in: claim immediately. Signed-out: Clerk modal.
    // Hide both branches until Clerk hydrates so the button doesn't flash
    // from "modal trigger" to "active claim" (or vice versa) on load.
    if (!isLoaded) {
      saveContent = (
        <button disabled className="btn-primary opacity-40 cursor-default">
          SAVE BUILD
        </button>
      );
    } else if (isSignedIn) {
      saveContent = (
        <button
          onClick={() => startTransition(claimBuild)}
          disabled={pending}
          className="btn-primary disabled:opacity-50"
        >
          SAVE BUILD
        </button>
      );
    } else {
      saveContent = (
        <SignInButton mode="modal">
          <button className="btn-primary">SAVE BUILD</button>
        </SignInButton>
      );
    }
  }

  return (
    <div className="mt-10 pt-6 hairline-t flex flex-wrap items-center gap-4">
      <p className="eyebrow text-[10px] mr-auto">[ACTIONS]</p>
      {saveContent}
      {!isLoaded ? (
        <button disabled className="btn-ghost py-2.5 px-4 opacity-40 cursor-default">
          SHARE BUILD
        </button>
      ) : isSignedIn ? (
        <button onClick={copyShareLink} className="btn-ghost py-2.5 px-4">
          SHARE BUILD
        </button>
      ) : (
        <SignInButton mode="modal">
          <button className="btn-ghost py-2.5 px-4">SHARE BUILD</button>
        </SignInButton>
      )}
      {toast && (
        <span
          role="status"
          className="text-[11px] tracking-[0.1em] uppercase font-[family-name:var(--font-mono)] text-signal"
        >
          {toast}
        </span>
      )}
    </div>
  );
}
