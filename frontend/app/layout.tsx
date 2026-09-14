import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "WorkLytix AI",
  description:
    "WorkLytix AI turns workout data into deterministic analytics and AI-powered interpretation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark ${dmSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <SiteHeader />
        {children}
        <footer className="mx-auto w-full max-w-6xl px-4 pb-8 sm:px-6">
          <p className="text-center text-xs text-muted-foreground">
            <span className="font-brand text-sm text-[#F5F5F5]">
              WorkLytix AI
            </span>{" "}
            · deterministic training analytics
          </p>
        </footer>
      </body>
    </html>
  );
}
