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
      <Sidebar />
      <TopBar />
      <main
        id="main-content"
        className={`pt-20 px-4 pb-4 lg:px-6 lg:pb-6 min-h-screen transition-[margin-left] duration-200 ${
          collapsed ? "lg:ml-16" : "lg:ml-60"
        }`}
      >
        {children}
      </main>
    </ToastProvider>
  );
}
