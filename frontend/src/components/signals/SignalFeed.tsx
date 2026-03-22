"use client";
import { useSignals } from "@/hooks/useSignals";
import SignalCard from "./SignalCard";
import EmptyState from "@/components/ui/EmptyState";

interface Props { limit?: number; compact?: boolean }
export function SignalFeed({ limit, compact }: Props) {
  const { signals, loading } = useSignals();
  const displayed = limit ? signals.slice(0, limit) : signals;
  if (loading) return <div className="bg-surface border border-border rounded-lg p-5"><div className="animate-pulse h-20 bg-elevated rounded" /></div>;
  if (!displayed.length) return <div className="bg-surface border border-border rounded-lg p-5"><EmptyState message="No signals generated yet." /></div>;
  return (
    <div className={`bg-surface border border-border rounded-lg p-4 ${compact ? "" : ""}`}>
      <h3 className="text-card-title text-primary mb-3">Recent Signals</h3>
      <div className="space-y-2">{displayed.map(s => <SignalCard key={s.id} signal={s} />)}</div>
    </div>
  );
}
