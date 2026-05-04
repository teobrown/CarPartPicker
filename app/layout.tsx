import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import "./globals.css";

// Use Clerk's official `dark` base theme for readable contrast on every
// element (labels, helper text, divider lines, secondary buttons).
// Earlier we hand-tuned variables and ended up with low-contrast
// helper/secondary text that was hard to read. The signal-amber accent
// and the square corners (borderRadius=0) layer on top of the dark base
// without touching the other 30+ palette tokens Clerk manages.
const clerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "#F5C535",
    borderRadius: "0",
  },
};

const bricolage = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  axes: ["opsz"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

// description is what shows up under the title in iMessage/Slack/Discord
// link cards and in Google search results. Lead with the elevator pitch
// and keep it under ~155 chars so it doesn't get truncated. The OG image
// (app/opengraph-image.tsx) handles the visual side of link cards.
const SHARE_DESCRIPTION =
  "Pick your car. Get a compatibility-checked catalog of bolt-ons, suspension, wheels, and body mods. Build your car without the forum tabs.";

export const metadata: Metadata = {
  title: {
    default: "Carbuildr — Pit Wall",
    template: "%s · Carbuildr",
  },
  description: SHARE_DESCRIPTION,
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  openGraph: {
    title: "Carbuildr — Pit Wall",
    description: SHARE_DESCRIPTION,
    type: "website",
    siteName: "Carbuildr",
  },
  twitter: {
    card: "summary_large_image",
    title: "Carbuildr — Pit Wall",
    description: SHARE_DESCRIPTION,
  },
  // Impact Radius affiliate-network site verification. Renders as
  //   <meta name="impact-site-verification" content="...">
  // Their docs example uses `value=`, but the HTML standard is `content=`
  // and Impact's verifier accepts it. If they ever flag verification
  // failure, swap to an inline JSX <meta> with the literal `value` attr.
  other: {
    "impact-site-verification": "44264c6e-3e57-4447-be1e-18982c8f6457",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${bricolage.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg text-fg">
        <ClerkProvider appearance={clerkAppearance}>
          <div className="grain-overlay" aria-hidden="true" />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
