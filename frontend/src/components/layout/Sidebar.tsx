"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  Gauge,
  Crosshair,
  ArrowLeftRight,
  LineChart,
  SlidersHorizontal,
  Menu,
  X,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import StatusDot from "@/components/ui/StatusDot";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Gauge;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/signals", label: "Signals", icon: Crosshair },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/analytics", label: "Analytics", icon: LineChart },
  { href: "/settings", label: "Settings", icon: SlidersHorizontal },
];

const COLLAPSED_KEY = "lumitrade-sidebar-collapsed";

const SIDEBAR_EXPANDED = 240;
const SIDEBAR_COLLAPSED = 64;

/** Spring config for sidebar width and indicator transitions */
const sidebarSpring = { type: "spring" as const, stiffness: 300, damping: 30 };
const indicatorSpring = { type: "spring" as const, stiffness: 400, damping: 35 };

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const navRefs = useRef<Map<string, HTMLAnchorElement>>(new Map());
  const prefersReducedMotion = useReducedMotion();

  const statusDotPulse = prefersReducedMotion
    ? undefined
    : {
        boxShadow: [
          "0 0 0px 0px var(--color-profit)",
          "0 0 3px 1px var(--color-profit)",
          "0 0 0px 0px var(--color-profit)",
        ],
      };
  const statusDotTransition = prefersReducedMotion
    ? undefined
    : { duration: 2, repeat: Infinity, ease: "easeInOut" as const };

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

  /** Find the active nav item index for the indicator position */
  const activeIndex = NAV_ITEMS.findIndex((item) =>
    pathname?.startsWith(item.href)
  );

  const sidebarContent = (isCollapsed: boolean) => (
    <>
      {/* Logo */}
      <div
        className={`flex items-center ${isCollapsed ? "justify-center px-2 py-5" : "justify-between px-5 py-6"}`}
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isCollapsed ? (
            <motion.span
              key="logo-collapsed"
              className="text-sm font-bold tracking-tight"
              style={{ color: "var(--color-brand)" }}
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
                style={{ color: "var(--color-brand)" }}
              >
                LUMITRADE
              </span>
              <p
                className="mt-0.5 text-[10px] font-mono"
                style={{ color: "var(--color-text-tertiary)" }}
              >
                AI Trading Platform
              </p>
            </motion.div>
          )}
        </AnimatePresence>
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
      <nav className="relative flex-1 overflow-y-auto scrollbar-hide px-2 py-4 space-y-0.5">
        {/* Animated active indicator bar (desktop expanded only) */}
        {!isCollapsed && activeIndex >= 0 && (
          <motion.div
            className="absolute left-0 w-[2px] rounded-r-full"
            style={{
              height: 36,
              background: "var(--color-brand)",
            }}
            animate={{
              top: activeIndex * 36 + 16, // 36px per item + 16px nav padding
            }}
            transition={indicatorSpring}
            layoutId="active-indicator"
          />
        )}

        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);

          return (
            <motion.div
              key={href}
              whileHover={{
                x: isCollapsed ? 0 : 2,
                backgroundColor: active
                  ? "transparent"
                  : "var(--color-bg-elevated)",
              }}
              transition={{ duration: 0.15 }}
              className="rounded-lg"
            >
              <Link
                ref={(el) => {
                  if (el) navRefs.current.set(href, el);
                }}
                href={href}
                title={isCollapsed ? label : undefined}
                className={`flex items-center ${isCollapsed ? "justify-center" : "gap-3"} ${isCollapsed ? "px-0 py-2.5" : "px-3 py-2.5"} rounded-lg text-sm`}
                style={
                  active
                    ? {
                        background: "var(--color-brand-dim)",
                        color: "var(--color-text-primary)",
                      }
                    : {
                        color: "var(--color-text-secondary)",
                      }
                }
              >
                <Icon size={isCollapsed ? 20 : 16} />
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
              </Link>
            </motion.div>
          );
        })}
      </nav>

      {/* Collapse toggle (desktop only) */}
      <motion.button
        onClick={toggleCollapsed}
        className="hidden lg:flex items-center justify-center py-2 mx-2 mb-2 rounded-lg"
        style={{ color: "var(--color-text-tertiary)" }}
        whileHover={{ backgroundColor: "var(--color-bg-elevated)" }}
        transition={{ duration: 0.15 }}
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {isCollapsed ? (
          <ChevronsRight size={16} />
        ) : (
          <ChevronsLeft size={16} />
        )}
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

      {/* Bottom status section */}
      <div
        className={`${isCollapsed ? "px-2 py-3" : "px-4 py-4"} space-y-3`}
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-center gap-2">
          <span
            className={`text-xs font-label px-2 py-0.5 rounded bg-warning-dim text-warning ${isCollapsed ? "text-[9px] px-1" : ""}`}
          >
            PAPER
          </span>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          {!isCollapsed ? (
            <motion.div
              key="status-expanded"
              className="flex items-center gap-2 text-xs"
              style={{ color: "var(--color-text-tertiary)" }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
            >
              <motion.span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: "var(--color-profit)" }}
                animate={statusDotPulse}
                transition={statusDotTransition}
              />
              <span>All systems online</span>
            </motion.div>
          ) : (
            <motion.div
              key="status-collapsed"
              className="flex justify-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
            >
              <motion.span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: "var(--color-profit)" }}
                animate={statusDotPulse}
                transition={statusDotTransition}
              />
            </motion.div>
          )}
        </AnimatePresence>
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
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-40 bg-[#0D1B2A]/70 backdrop-blur-sm lg:hidden"
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
              background: "var(--color-bg-surface)",
              backdropFilter: "var(--glass-blur)",
              WebkitBackdropFilter: "var(--glass-blur)",
              borderRight: "1px solid var(--color-border)",
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

      {/* Desktop sidebar with animated width */}
      <motion.aside
        className="hidden lg:flex fixed left-0 top-0 z-50 min-h-screen flex-col"
        style={{
          background: "var(--color-bg-surface)",
          backdropFilter: "var(--glass-blur)",
          WebkitBackdropFilter: "var(--glass-blur)",
          borderRight: "1px solid var(--color-border)",
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
