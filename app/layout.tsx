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

export const metadata: Metadata = {
  title: {
    default: "CarPartPicker — Pit Wall",
    template: "%s · CarPartPicker",
  },
  description:
    "PCPartPicker for tuner cars. Compatibility-checked mod builds with affiliate buy-through.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  openGraph: {
    title: "CarPartPicker — Pit Wall",
    description:
      "PCPartPicker for tuner cars. Compatibility-checked mod builds with affiliate buy-through.",
    type: "website",
    siteName: "CarPartPicker",
  },
  twitter: {
    card: "summary_large_image",
    title: "CarPartPicker — Pit Wall",
    description:
      "PCPartPicker for tuner cars. Compatibility-checked mod builds with affiliate buy-through.",
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
