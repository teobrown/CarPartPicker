"use client";

import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex-1 mx-auto max-w-[1400px] px-6 py-32 text-center">
      <p className="eyebrow text-danger mb-4">[ERR] · UNEXPECTED FAULT</p>
      <h1 className="display-lg">
        Something broke<span className="text-signal">.</span>
      </h1>
      <p className="body-sm mt-3 font-[family-name:var(--font-mono)] text-fg-muted max-w-xl mx-auto">
        {error.message || "Unknown error"}
      </p>
      <div className="mt-10 flex items-center gap-4 justify-center">
        <button onClick={() => reset()} className="btn-primary">
          RETRY
        </button>
        <Link href="/" className="arrow-link">
          Home
        </Link>
      </div>
    </main>
  );
}
