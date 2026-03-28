interface Props { action: string }
export default function Badge({ action }: Props) {
  const styles: Record<string, string> = {
    BUY: "bg-profit-dim text-profit", SELL: "bg-loss-dim text-loss", HOLD: "bg-warning-dim text-warning",
  };
  return <span className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${styles[action] || "bg-elevated text-secondary"}`}>{action}</span>;
}
