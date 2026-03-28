"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import { ToastProvider } from "@/components/ui/Toast";

const COLLAPSED_KEY = "lumitrade-sidebar-collapsed";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const check = () => {
      setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "true");
    };
    check();
    // Listen for storage changes (when sidebar toggles)
    window.addEventListener("storage", check);
    // Also poll since same-tab storage events don't fire
    const interval = setInterval(check, 300);
    return () => {
      window.removeEventListener("storage", check);
      clearInterval(interval);
    };
  }, []);

  return (
    <ToastProvider>
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Sidebar />
      <TopBar />
      <main
        id="main-content"
        className={`pt-16 px-5 pb-6 lg:px-7 lg:pb-8 min-h-screen max-w-[1600px] transition-[margin-left] duration-200 ${
          collapsed ? "lg:ml-16" : "lg:ml-60"
        }`}
      >
        {children}
      </main>
    </ToastProvider>
  );
}
