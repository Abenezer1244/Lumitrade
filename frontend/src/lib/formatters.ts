export function formatPrice(price: string | number, pair?: string): string {
  const n = typeof price === "string" ? parseFloat(price) : price;
  if (isNaN(n)) return "\u2014";
  const decimals = pair?.includes("JPY") ? 3 : 5;
  return n.toFixed(decimals);
}

export function formatPnl(value: string | number | null): { formatted: string; colorClass: string } {
  if (value === null || value === undefined) return { formatted: "\u2014", colorClass: "text-tertiary" };
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(n)) return { formatted: "\u2014", colorClass: "text-tertiary" };
  const sign = n >= 0 ? "+" : "";
  return {
    formatted: `${sign}$${Math.abs(n).toFixed(2)}`,
    colorClass: n > 0 ? "text-profit" : n < 0 ? "text-loss" : "text-secondary",
  };
}

export function formatPips(pips: string | number | null): string {
  if (pips === null || pips === undefined) return "\u2014";
  const n = typeof pips === "string" ? parseFloat(pips) : pips;
  if (isNaN(n)) return "\u2014";
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}p`;
}

export function formatPair(pair: string): string {
  return pair.replace("_", "/");
}

export function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

export function formatDuration(minutes: number | null): string {
  if (!minutes) return "\u2014";
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}
