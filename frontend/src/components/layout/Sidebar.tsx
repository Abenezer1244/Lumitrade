"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Zap, History, BarChart2, Settings, BookOpen, MessageCircle, TrendingUp, Store, Users, FlaskConical, Key } from "lucide-react";
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
  return (
    <aside className="w-60 min-h-screen bg-surface border-r border-border flex flex-col fixed left-0 top-0 z-30">
      <div className="px-5 py-6 border-b border-border">
        <span className="font-display text-xl font-semibold text-gold tracking-wide">LUMITRADE</span>
        <p className="text-tertiary text-xs mt-0.5 font-mono">v1.0 · Phase 0</p>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon, phase }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link key={href} href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-all duration-150 ${
                active ? "bg-elevated text-primary border-l-2 border-accent pl-[10px]" : "text-secondary hover:text-primary hover:bg-elevated/50"
              }`}>
              <Icon size={16} />
              <span className="font-medium flex-1">{label}</span>
              {phase > 0 && <span className="text-[10px] text-tertiary">P{phase}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-4 border-t border-border space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-label px-2 py-0.5 rounded bg-warning-dim text-warning">PAPER</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-tertiary">
          <StatusDot status="healthy" />
          <span>All systems online</span>
        </div>
      </div>
    </aside>
  );
}
