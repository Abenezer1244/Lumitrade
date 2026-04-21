"use client";

import { Download } from "lucide-react";
import type { Trade } from "@/types/trading";

interface ExportButtonProps {
  trades: Trade[];
}

function escapeCsvField(field: string): string {
  if (field.includes(",") || field.includes('"') || field.includes("\n")) {
    return `"${field.replace(/"/g, '""')}"`;
  }
  return field;
}

function formatDurationForCsv(minutes: number | null): string {
  if (!minutes) return "";
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export default function ExportButton({ trades }: ExportButtonProps) {
  const isEmpty = trades.length === 0;

  function handleExport() {
    if (isEmpty) return;

    const headers = [
      "Date",
      "Pair",
      "Direction",
      "Entry",
      "Exit",
      "P&L ($)",
      "P&L (pips)",
      "Duration",
      "Outcome",
    ];

    const rows = trades.map((t) => [
      t.opened_at,
      t.pair.replace("_", "/"),
      t.direction,
      t.entry_price,
      t.exit_price ?? "",
      t.pnl_usd ?? "",
      t.pnl_pips ?? "",
      formatDurationForCsv(t.duration_minutes),
      t.outcome ?? "",
    ]);

    const csvContent = [
      headers.map(escapeCsvField).join(","),
      ...rows.map((row) => row.map(escapeCsvField).join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const dateStr = new Date().toISOString().slice(0, 10);
    const link = document.createElement("a");
    link.href = url;
    link.download = `lumitrade-trades-${dateStr}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <button
      onClick={handleExport}
      disabled={isEmpty}
      className={`flex items-center gap-2 glass-elevated px-3 py-2 text-sm text-secondary hover:text-primary transition-colors ${
        isEmpty ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
      }`}
      aria-label="Export trades to CSV"
    >
      <Download size={14} />
      Export CSV
    </button>
  );
}
