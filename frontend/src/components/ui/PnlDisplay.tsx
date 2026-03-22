import { formatPnl } from "@/lib/formatters";
interface Props { value: string | number | null; size?: "sm" | "lg" }
export default function PnlDisplay({ value, size = "sm" }: Props) {
  const { formatted, colorClass } = formatPnl(value);
  const sizeClass = size === "lg" ? "text-metric" : "text-sm";
  return <span className={`font-mono ${sizeClass} ${colorClass}`}>{formatted}</span>;
}
