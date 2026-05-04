import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import "./globals.css";

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
        <div className="grain-overlay" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}
