"use client";

import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body className="min-h-screen bg-bg text-fg flex flex-col items-center justify-center px-6 text-center">
        <p className="eyebrow text-danger">[ERR] · UNEXPECTED FAULT</p>
        <h1 className="display-lg mt-4">
          Something broke<span className="text-signal">.</span>
        </h1>
        <p className="body mt-3 font-[family-name:var(--font-mono)] text-sm text-fg-muted max-w-xl">
          {error.message || "Unknown error"}
        </p>
        <div className="mt-8 flex gap-4">
          <button onClick={() => reset()} className="btn-primary">
            RETRY
          </button>
          <Link href="/" className="arrow-link">
            Home
          </Link>
        </div>
      </body>
    </html>
  );
}
