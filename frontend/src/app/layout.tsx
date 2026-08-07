import type { Metadata } from "next";
import { Newsreader, Space_Grotesk, Sora, Martian_Mono } from "next/font/google";
import { NeuroBackground } from "@/components/neuro-background";
import { HealthFooter } from "@/components/health-footer";
import "./globals.css";

const displayFont = Newsreader({
  variable: "--font-display",
  weight: ["400", "500"],
  style: ["normal", "italic"],
  subsets: ["latin"],
});

const bodyFont = Space_Grotesk({
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const dataFont = Sora({
  variable: "--font-data",
  weight: ["600", "700"],
  subsets: ["latin"],
});

const monoFont = Martian_Mono({
  variable: "--font-mono",
  weight: ["400", "500", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NeuLitTrace",
  description: "Rare-case-weighted literature retrieval for PET and neuroimaging findings.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displayFont.variable} ${bodyFont.variable} ${dataFont.variable} ${monoFont.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-void text-ink">
        <div className="ambient-glow" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="ambient-grain" aria-hidden="true" />
        <NeuroBackground />
        {children}
        <HealthFooter />
      </body>
    </html>
  );
}
