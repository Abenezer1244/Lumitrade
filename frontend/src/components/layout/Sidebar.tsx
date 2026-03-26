"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import {
  LayoutDashboard,
  Zap,
  History,
  BarChart2,
  Settings,
  Menu,
  X,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import StatusDot from "@/components/ui/StatusDot";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/trades", label: "Trades", icon: History },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

const COLLAPSED_KEY = "lumitrade-sidebar-collapsed";

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Restore collapsed state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(COLLAPSED_KEY);
    if (saved === "true") setCollapsed(true);
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }, []);

  // Close mobile sidebar on route change
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
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const sidebarContent = (isCollapsed: boolean) => (
    <>
      {/* Logo */}
      <div
        className={`flex items-center ${isCollapsed ? "justify-center px-2 py-5" : "justify-between px-5 py-6"}`}
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        {isCollapsed ? (
          <span
            className="font-mono text-sm font-bold"
            style={{ color: "var(--color-brand)" }}
          >
            LT
          </span>
        ) : (
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
        )}
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
      <nav className="flex-1 overflow-y-auto scrollbar-hide px-2 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              title={isCollapsed ? label : undefined}
              className={`flex items-center ${isCollapsed ? "justify-center" : "gap-3"} ${isCollapsed ? "px-0 py-2.5" : "px-3 py-2.5"} rounded-lg text-sm transition-all duration-150`}
              style={
                active
                  ? {
                      background: "var(--color-brand-dim)",
                      borderLeft: isCollapsed ? "none" : "2px solid var(--color-brand)",
                      paddingLeft: isCollapsed ? undefined : "10px",
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
              <Icon size={isCollapsed ? 20 : 16} />
              {!isCollapsed && <span className="flex-1 font-medium">{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle (desktop only) */}
      <button
        onClick={toggleCollapsed}
        className="hidden lg:flex items-center justify-center py-2 mx-2 mb-2 rounded-lg transition-colors hover:bg-elevated"
        style={{ color: "var(--color-text-tertiary)" }}
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {isCollapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        {!isCollapsed && (
          <span className="ml-2 text-xs">Collapse</span>
        )}
      </button>

      {/* Bottom status section */}
      <div
        className={`${isCollapsed ? "px-2 py-3" : "px-4 py-4"} space-y-3`}
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-center gap-2">
          <span className={`text-xs font-label px-2 py-0.5 rounded bg-warning-dim text-warning ${isCollapsed ? "text-[9px] px-1" : ""}`}>
            PAPER
          </span>
        </div>
        {!isCollapsed && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            <StatusDot status="healthy" />
            <span>All systems online</span>
          </div>
        )}
        {isCollapsed && (
          <div className="flex justify-center">
            <StatusDot status="healthy" />
          </div>
        )}
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
        className={`fixed left-0 top-0 z-50 flex min-h-screen flex-col transition-all duration-200 ease-out lg:translate-x-0 ${
          mobileOpen ? "translate-x-0 w-60" : "-translate-x-full w-60"
        } ${collapsed ? "lg:w-16" : "lg:w-60"}`}
        style={{
          background: "var(--color-bg-surface)",
          backdropFilter: "var(--glass-blur)",
          WebkitBackdropFilter: "var(--glass-blur)",
          borderRight: "1px solid var(--color-border)",
        }}
        aria-label="Main navigation"
      >
        {/* Mobile always shows expanded, desktop respects collapsed state */}
        <div className="lg:hidden">{sidebarContent(false)}</div>
        <div className="hidden lg:flex lg:flex-col lg:h-screen">
          {sidebarContent(collapsed)}
        </div>
      </aside>
    </>
  );
}
