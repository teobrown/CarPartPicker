import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Security headers applied to every response. Vercel's defaults set
  // Strict-Transport-Security; we layer on the rest. Codex review-6
  // flagged missing anti-framing as a clickjacking risk on the build
  // editor (Save/Share buttons live there — a clickjack frame could
  // trick a signed-in user into claiming/sharing an attacker's build).
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Block all framing. CSP frame-ancestors is the modern form;
          // X-Frame-Options is the legacy fallback for old browsers
          // that ignore CSP. 'none' = never embed in any frame.
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "X-Frame-Options", value: "DENY" },
          // Stop browsers from sniffing a non-declared MIME type — kills
          // a class of "upload an image, browser executes it as JS" bugs.
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Send the full referrer same-origin, only the origin cross-
          // origin. Default for same-origin analytics; doesn't leak query
          // strings (which could contain build slugs) to vendor sites.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Lock down browser APIs we don't use. Reduces blast radius if
          // a script slips in via a vendor CDN compromise.
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
