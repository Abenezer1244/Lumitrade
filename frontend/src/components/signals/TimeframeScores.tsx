interface Props { scores: { h4: number; h1: number; m15: number } }
export default function TimeframeScores({ scores }: Props) {
  const bars = [
    { label: "H4", value: scores.h4, weight: "0.40" },
    { label: "H1", value: scores.h1, weight: "0.35" },
    { label: "M15", value: scores.m15, weight: "0.25" },
  ];
  return (
    <div className="space-y-2">
      {bars.map(({ label, value, weight }) => {
        const pct = Math.round(value * 100);
        const color = pct >= 80 ? "bg-profit" : pct >= 60 ? "bg-warning" : "bg-loss";
        return (
          <div key={label} className="flex items-center gap-3">
            <span className="text-xs text-tertiary w-8 font-mono">{label}</span>
            <div className="flex-1 h-1.5 bg-elevated rounded-full overflow-hidden">
              <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs font-mono text-secondary w-8 text-right">{pct}%</span>
            <span className="text-[10px] text-tertiary w-8">{weight}</span>
          </div>
        );
      })}
    </div>
  );
}
