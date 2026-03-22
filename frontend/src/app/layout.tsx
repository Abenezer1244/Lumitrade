import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lumitrade",
  description: "AI-Powered Forex Trading Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
