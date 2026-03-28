"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  LayoutDashboard, Zap, History, BarChart2, Settings, Menu, X,
  ChevronsLeft, ChevronsRight, BookOpen, MessageCircle, TrendingUp,
  Store, Users, FlaskConical, Key,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  phase?: number;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/trades", label: "Trades", icon: History },
  { href: "/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/journal", label: "Journal", icon: BookOpen, phase: 2 },
  { href: "/coach", label: "AI Coach", icon: MessageCircle, phase: 2 },
  { href: "/intelligence", label: "Intel Report", icon: TrendingUp, phase: 2 },
  { href: "/marketplace", label: "Marketplace", icon: Store, phase: 3 },
  { href: "/copy", label: "Copy Trading", icon: Users, phase: 3 },
  { href: "/backtest", label: "Backtest", icon: FlaskConical, phase: 3 },
  { href: "/api-keys", label: "API Access", icon: Key, phase: 3 },
];

const COLLAPSED_KEY = "lumitrade-sidebar-collapsed";
const SIDEBAR_EXPANDED = 240;
const SIDEBAR_COLLAPSED = 64;
const sidebarSpring = { type: "spring" as const, stiffness: 300, damping: 30 };
const indicatorSpring = { type: "spring" as const, stiffness: 400, damping: 35 };

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const navRefs = useRef<Map<string, HTMLAnchorElement>>(new Map());

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

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const activeIndex = NAV_ITEMS.findIndex((item) => pathname?.startsWith(item.href));

  const sidebarContent = (isCollapsed: boolean) => (
    <>
      {/* Logo */}
      <div
        className={`flex items-center ${isCollapsed ? "justify-center px-2 py-5" : "justify-between px-5 py-5"}`}
        style={{ borderBottom: "1px solid rgba(30, 55, 92, 0.25)" }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isCollapsed ? (
            <motion.span
              key="logo-collapsed"
              className="text-sm font-bold"
              style={{
                background: "var(--gradient-accent)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                fontFamily: "'JetBrains Mono', monospace",
              }}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.15 }}
            >
              LT
            </motion.span>
          ) : (
            <motion.div
              key="logo-expanded"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
            >
              <span
                className="text-lg font-bold tracking-tight"
                style={{
                  background: "var(--gradient-accent)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
              >
                LUMITRADE
              </span>
              <p className="mt-0.5 text-[10px] font-mono" style={{ color: "var(--color-text-tertiary)" }}>
                AI Trading Platform
              </p>
            </motion.div>
          )}
        </AnimatePresence>
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-lg transition-colors"
          style={{ color: "var(--color-text-secondary)" }}
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="relative flex-1 overflow-y-auto scrollbar-hide px-2 py-3 space-y-0.5">
        {!isCollapsed && activeIndex >= 0 && (
          <motion.div
            className="absolute left-0 w-[2px] rounded-r-full"
            style={{ height: 36, background: "var(--gradient-accent)" }}
            animate={{ top: activeIndex * 36 + 12 }}
            transition={indicatorSpring}
            layoutId="active-indicator"
          />
        )}

        {NAV_ITEMS.map(({ href, label, icon: Icon, phase }) => {
          const active = pathname?.startsWith(href);
          const isFuture = !!phase;

          return (
            <motion.div
              key={href}
              whileHover={{
                x: isCollapsed ? 0 : 2,
                backgroundColor: active ? "transparent" : "rgba(18, 30, 52, 0.5)",
              }}
              transition={{ duration: 0.15 }}
              className="rounded-lg"
            >
              <Link
                ref={(el) => { if (el) navRefs.current.set(href, el); }}
                href={href}
                title={isCollapsed ? `${label}${phase ? ` (Phase ${phase})` : ""}` : undefined}
                className={`flex items-center ${isCollapsed ? "justify-center" : "gap-3"} ${isCollapsed ? "px-0 py-2.5" : "px-3 py-2.5"} rounded-lg text-sm transition-colors`}
                style={
                  active
                    ? {
                        background: "var(--gradient-accent-subtle)",
                        color: "var(--color-text-primary)",
                      }
                    : {
                        color: isFuture ? "var(--color-text-tertiary)" : "var(--color-text-secondary)",
                        opacity: isFuture ? 0.5 : 1,
                      }
                }
              >
                <Icon size={isCollapsed ? 20 : 16} style={active ? { color: "var(--color-accent)" } : undefined} />
                <AnimatePresence mode="wait" initial={false}>
                  {!isCollapsed && (
                    <motion.span
                      key={`label-${href}`}
                      className="flex-1 font-medium whitespace-nowrap overflow-hidden"
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.15 }}
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
                <AnimatePresence initial={false}>
                  {!isCollapsed && phase && (
                    <motion.span
                      key={`phase-${href}`}
                      className="text-[8px] font-mono px-1.5 py-0.5 rounded-full"
                      style={{ background: "rgba(18, 30, 52, 0.6)", color: "var(--color-text-tertiary)" }}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.12 }}
                    >
                      P{phase}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Link>
            </motion.div>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <motion.button
        onClick={toggleCollapsed}
        className="hidden lg:flex items-center justify-center py-2 mx-2 mb-2 rounded-lg"
        style={{ color: "var(--color-text-tertiary)" }}
        whileHover={{ backgroundColor: "rgba(18, 30, 52, 0.5)" }}
        transition={{ duration: 0.15 }}
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {isCollapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        <AnimatePresence initial={false}>
          {!isCollapsed && (
            <motion.span
              className="ml-2 text-xs whitespace-nowrap overflow-hidden"
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15 }}
            >
              Collapse
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>

      {/* Bottom status */}
      <div
        className={`${isCollapsed ? "px-2 py-3" : "px-4 py-3"} space-y-2`}
        style={{ borderTop: "1px solid rgba(30, 55, 92, 0.2)" }}
      >
        <div className="flex items-center justify-center">
          <span
            className={`text-[10px] font-bold tracking-widest px-2.5 py-0.5 rounded-full ${isCollapsed ? "text-[8px] px-1.5" : ""}`}
            style={{ background: "rgba(255, 179, 71, 0.1)", color: "var(--color-warning)" }}
          >
            PAPER
          </span>
        </div>
        <div className={`flex items-center ${isCollapsed ? "justify-center" : "gap-2"}`}>
          <motion.span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: "var(--color-profit)" }}
            animate={{
              boxShadow: [
                "0 0 0px 0px rgba(0, 200, 150, 0)",
                "0 0 6px 2px rgba(0, 200, 150, 0.4)",
                "0 0 0px 0px rgba(0, 200, 150, 0)",
              ],
            }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          />
          <AnimatePresence mode="wait" initial={false}>
            {!isCollapsed && (
              <motion.span
                key="status-text"
                className="text-[10px]"
                style={{ color: "var(--color-text-tertiary)" }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.12 }}
              >
                Systems online
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile hamburger */}
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
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-40 lg:hidden"
            style={{ backgroundColor: "rgba(0, 0, 0, 0.6)" }}
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}
      </AnimatePresence>

      {/* Mobile sidebar */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.aside
            className="fixed left-0 top-0 z-50 flex min-h-screen w-60 flex-col lg:hidden"
            style={{
              background: "var(--color-bg-surface-solid)",
              borderRight: "1px solid rgba(30, 55, 92, 0.25)",
            }}
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", stiffness: 350, damping: 35 }}
            aria-label="Main navigation"
          >
            {sidebarContent(false)}
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Desktop sidebar */}
      <motion.aside
        className="hidden lg:flex fixed left-0 top-0 z-50 min-h-screen flex-col"
        style={{
          background: "var(--color-bg-surface-solid)",
          borderRight: "1px solid rgba(30, 55, 92, 0.2)",
        }}
        animate={{ width: collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED }}
        transition={sidebarSpring}
        aria-label="Main navigation"
      >
        {sidebarContent(collapsed)}
      </motion.aside>
    </>
  );
}
