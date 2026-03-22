import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

export const metadata: Metadata = { title: "Lumitrade", description: "AI-Powered Forex Trading Platform" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Sidebar />
        <main className="ml-60 p-6 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
