"use client";
import { useSignals } from "@/hooks/useSignals";
import { Zap } from "lucide-react";
import SignalCard from "./SignalCard";
import EmptyState from "@/components/ui/EmptyState";

interface Props { limit?: number; compact?: boolean }
export function SignalFeed({ limit, compact }: Props) {
  const { signals, loading } = useSignals();
  const displayed = limit ? signals.slice(0, limit) : signals;
  if (loading) return <div className="glass p-5"><div className="animate-pulse h-20 bg-elevated rounded-lg" /></div>;
  if (!displayed.length) return <div className="glass p-5"><EmptyState icon={Zap} message="No signals generated yet." description="Signals will appear here when the AI generates trading opportunities." /></div>;
  return (
    <div className={`glass p-4 ${compact ? "" : ""}`}>
      <h3 className="text-card-title text-primary mb-3">Recent Signals</h3>
      <div className="space-y-2" aria-live="polite" aria-relevant="additions">{displayed.map(s => <SignalCard key={s.id} signal={s} />)}</div>
    </div>
  );
}
