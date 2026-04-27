export function formatPrice(price: string | number, pair?: string): string {
  const n = typeof price === "string" ? parseFloat(price) : price;
  if (isNaN(n)) return "\u2014";
  // JPY pairs quote to 3dp, gold (XAU) to 2dp, all other FX to 5dp.
  // Single source of truth for instrument-precision rendering.
  const decimals = pair?.includes("JPY") ? 3 : pair?.includes("XAU") ? 2 : 5;
  return n.toFixed(decimals);
}

/**
 * Signed-USD formatter that mirrors the inline pattern used across the
 * dashboard: positive/zero values get a leading "+", negatives render as
 * "$X.XX" with no leading sign (loss color is conveyed via CSS class on the
 * surrounding span, not via a minus glyph). Returns "\u2014" (em-dash) for
 * null/undefined/NaN so the UI can distinguish "no data" from "$0.00".
 */
export function formatSignedUsd(
  value: number | string | null | undefined,
  opts?: { decimals?: number },
): string {
  if (value === null || value === undefined) return "\u2014";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(n)) return "\u2014";
  const decimals = opts?.decimals ?? 2;
  const sign = n >= 0 ? "+" : "";
  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
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
  const hh = date.getUTCHours().toString().padStart(2, "0");
  const mm = date.getUTCMinutes().toString().padStart(2, "0");
  const ss = date.getUTCSeconds().toString().padStart(2, "0");

  // Same UTC day: show HH:MM:SS
  if (
    date.getUTCFullYear() === now.getUTCFullYear() &&
    date.getUTCMonth() === now.getUTCMonth() &&
    date.getUTCDate() === now.getUTCDate()
  ) {
    return `${hh}:${mm}:${ss}`;
  }
  // Different day: show Mon DD HH:MM
  const mon = date.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const dd = date.getUTCDate();
  return `${mon} ${dd} ${hh}:${mm}`;
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
