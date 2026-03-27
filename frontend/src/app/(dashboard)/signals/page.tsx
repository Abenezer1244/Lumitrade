"use client";
import { useState } from "react";
import { useSignals } from "@/hooks/useSignals";
import { Zap } from "lucide-react";
import SignalCard from "@/components/signals/SignalCard";
import EmptyState from "@/components/ui/EmptyState";

const PAIRS = ["All Pairs", "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD", "XAU_USD"];
const ACTIONS = ["All Actions", "BUY", "SELL", "HOLD"];

export default function SignalsPage() {
  const { signals, loading } = useSignals();
  const [pair, setPair] = useState("All Pairs");
  const [action, setAction] = useState("All Actions");

  const filtered = signals.filter((s) => {
    if (pair !== "All Pairs" && s.pair !== pair) return false;
    if (action !== "All Actions" && s.action !== action) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="glass p-4 flex flex-wrap items-center gap-3">
        <select
          value={pair}
          onChange={(e) => setPair(e.target.value)}
          className="bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-primary"
        >
          {PAIRS.map((p) => (
            <option key={p} value={p}>
              {p.replace("_", "/")}
            </option>
          ))}
        </select>
        <select
          value={action}
          onChange={(e) => setAction(e.target.value)}
          className="bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-primary"
        >
          {ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <span className="text-xs text-tertiary ml-auto">
          {filtered.length} signal{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Signal Feed */}
      {loading ? (
        <div className="glass p-5">
          <div className="animate-pulse h-20 bg-elevated rounded-lg" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass p-5">
          <EmptyState
            icon={Zap}
            message="No signals match your filters."
            description="Try adjusting the pair or action filter."
          />
        </div>
      ) : (
        <div className="glass p-4">
          <div className="space-y-2" aria-live="polite" aria-relevant="additions">
            {filtered.map((s) => (
              <SignalCard key={s.id} signal={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
