"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Zap,
  History,
  BarChart2,
  Settings,
  BookOpen,
  MessageCircle,
  TrendingUp,
  Store,
  Users,
  FlaskConical,
  Key,
  Menu,
  X,
} from "lucide-react";
import StatusDot from "@/components/ui/StatusDot";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, phase: 0 },
  { href: "/signals", label: "Signals", icon: Zap, phase: 0 },
  { href: "/trades", label: "Trades", icon: History, phase: 0 },
  { href: "/analytics", label: "Analytics", icon: BarChart2, phase: 0 },
  { href: "/settings", label: "Settings", icon: Settings, phase: 0 },
  { href: "/journal", label: "Journal", icon: BookOpen, phase: 2 },
  { href: "/coach", label: "AI Coach", icon: MessageCircle, phase: 2 },
  { href: "/intelligence", label: "Intel Report", icon: TrendingUp, phase: 2 },
  { href: "/marketplace", label: "Marketplace", icon: Store, phase: 3 },
  { href: "/copy", label: "Copy Trading", icon: Users, phase: 3 },
  { href: "/backtest", label: "Backtest", icon: FlaskConical, phase: 3 },
  { href: "/api-keys", label: "API Access", icon: Key, phase: 3 },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Close sidebar on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const sidebarContent = (
    <>
      {/* Logo */}
      <div
        className="px-5 py-6 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div>
          <span
            className="font-mono text-lg font-bold"
            style={{ color: "var(--color-brand)" }}
          >
            LUMITRADE
          </span>
          <p
            className="mt-0.5 font-mono text-xs"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            v1.0 · Phase 0
          </p>
        </div>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-lg hover:bg-elevated transition-colors"
          style={{ color: "var(--color-text-secondary)" }}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto scrollbar-hide px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon, phase }) => {
          const active = pathname?.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
              style={
                active
                  ? {
                      background: "var(--color-brand-dim)",
                      borderLeft: "2px solid var(--color-brand)",
                      paddingLeft: "10px",
                      color: "var(--color-text-primary)",
                    }
                  : {
                      color: "var(--color-text-secondary)",
                    }
              }
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "var(--color-text-primary)";
                  e.currentTarget.style.background = "var(--color-bg-elevated)";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.color = "var(--color-text-secondary)";
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              <Icon size={16} />
              <span className="flex-1 font-medium">{label}</span>
              {phase > 0 && (
                <span
                  className="text-[10px]"
                  style={{ color: "var(--color-text-tertiary)" }}
                >
                  P{phase}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom status section */}
      <div
        className="px-4 py-4 space-y-3"
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-label px-2 py-0.5 rounded bg-warning-dim text-warning">
            PAPER
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          <StatusDot status="healthy" />
          <span>All systems online</span>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-3.5 left-4 z-40 lg:hidden p-2 rounded-lg"
        style={{
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border)",
          color: "var(--color-text-primary)",
        }}
        aria-label="Open navigation"
        aria-expanded={mobileOpen}
      >
        <Menu size={18} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 z-50 flex w-60 min-h-screen flex-col transition-transform duration-200 ease-out lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{
          background: "var(--color-bg-surface)",
          backdropFilter: "var(--glass-blur)",
          WebkitBackdropFilter: "var(--glass-blur)",
          borderRight: "1px solid var(--color-border)",
        }}
        aria-label="Main navigation"
      >
        {sidebarContent}
      </aside>
    </>
  );
}
