import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

// Brand-tuned Clerk modal appearance. Match the brutalist editorial
// aesthetic of the rest of the site — near-black warm bg, signal amber
// accent, hairline borders, mono labels. Without these overrides the
// default Clerk modal looks mid-2020s SaaS and clashes with the brand.
const clerkAppearance = {
  variables: {
    colorPrimary: "#F5C535",
    colorBackground: "#1F1C19",
    colorText: "#ECE7DF",
    colorTextSecondary: "#8A8276",
    colorInputBackground: "#161310",
    colorInputText: "#ECE7DF",
    colorNeutral: "#5A554C",
    borderRadius: "0",
    fontFamily: "var(--font-display), system-ui, sans-serif",
  },
  elements: {
    card: { boxShadow: "none", border: "1px solid #3A352E" },
    formButtonPrimary: {
      textTransform: "uppercase" as const,
      letterSpacing: "0.14em",
      fontSize: "12px",
      color: "#1F1C19",
    },
    socialButtonsBlockButton: {
      border: "1px solid #3A352E",
      borderRadius: "0",
    },
    formFieldInput: {
      border: "1px solid #3A352E",
      borderRadius: "0",
    },
    footer: { background: "transparent" },
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
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider appearance={clerkAppearance}>
      <html
        lang="en"
        className={`${bricolage.variable} ${jetbrainsMono.variable} h-full antialiased`}
      >
        <body className="min-h-full flex flex-col bg-bg text-fg">
          <div className="grain-overlay" aria-hidden="true" />
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
