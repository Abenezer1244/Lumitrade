import type { Metadata } from "next";
import { ThemeProvider } from "@/components/ui/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lumitrade — AI-Powered Forex Trading",
  description: "Trade forex with AI precision. Lumitrade uses Claude AI to scan markets, generate explainable signals, and execute trades with 8 independent safety checks.",
  keywords: ["forex", "AI trading", "Claude AI", "OANDA", "trading signals", "risk management"],
  openGraph: {
    title: "Lumitrade — AI-Powered Forex Trading",
    description: "Trade forex with AI precision. Explainable signals, confidence scores, and automated risk management.",
    siteName: "Lumitrade",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Lumitrade — AI-Powered Forex Trading",
    description: "Trade forex with AI precision. Explainable signals, confidence scores, and automated risk management.",
  },
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
