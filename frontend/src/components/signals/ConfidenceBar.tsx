interface Props { value: number }
export default function ConfidenceBar({ value }: Props) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "bg-profit" : pct >= 65 ? "bg-warning" : "bg-loss";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-elevated rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-300 ease-out`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-secondary w-8 text-right">{pct}%</span>
    </div>
  );
}
