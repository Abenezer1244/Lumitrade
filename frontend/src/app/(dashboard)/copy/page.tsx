"use client";

import { Users, Shield, TrendingUp, Info } from "lucide-react";

interface LeaderboardTrader {
  rank: number;
  name: string;
  return90d: number;
  winRate: number;
  followers: number;
  riskScore: "Low" | "Medium" | "High";
}

const LEADERBOARD: LeaderboardTrader[] = [
  { rank: 1, name: "AlphaTrader_91", return90d: 34.2, winRate: 71, followers: 312, riskScore: "Low" },
  { rank: 2, name: "FXMaven", return90d: 28.7, winRate: 65, followers: 198, riskScore: "Medium" },
  { rank: 3, name: "TokyoScalp", return90d: 22.1, winRate: 74, followers: 156, riskScore: "Low" },
];

function RiskBadge({ score }: { score: LeaderboardTrader["riskScore"] }) {
  const colorMap: Record<string, string> = {
    Low: "var(--color-profit)",
    Medium: "var(--color-warning)",
    High: "var(--color-loss)",
  };
  const color = colorMap[score];

  return (
    <span
      className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{ backgroundColor: `${color}20`, color }}
    >
      {score}
    </span>
  );
}

export default function CopyPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: "var(--color-accent)", opacity: 0.15 }}
        >
          <Users size={20} style={{ color: "var(--color-accent)" }} />
        </div>
        <div>
          <h1
            className="text-xl font-bold"
            style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Copy Trading
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Follow top-performing traders and mirror their positions
          </p>
        </div>
      </div>

      {/* Leaderboard */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} style={{ color: "var(--color-profit)" }} />
          <h2
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
          >
            Top Traders — 90 Day
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                {["Rank", "Trader", "90d Return", "Win Rate", "Followers", "Risk Score", ""].map(
                  (header) => (
                    <th
                      key={header}
                      className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider"
                      style={{ color: "var(--color-text-tertiary)" }}
                    >
                      {header}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {LEADERBOARD.map((trader) => (
                <tr
                  key={trader.rank}
                  className="transition-colors"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <td className="py-3 px-3">
                    <span
                      className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold"
                      style={{
                        backgroundColor:
                          trader.rank === 1
                            ? "var(--color-warning)"
                            : "var(--color-bg-elevated)",
                        color:
                          trader.rank === 1
                            ? "var(--color-bg-primary)"
                            : "var(--color-text-secondary)",
                      }}
                    >
                      {trader.rank}
                    </span>
                  </td>
                  <td
                    className="py-3 px-3 font-mono text-sm font-medium"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {trader.name}
                  </td>
                  <td
                    className="py-3 px-3 font-mono text-sm font-bold"
                    style={{ color: "var(--color-profit)" }}
                  >
                    +{trader.return90d}%
                  </td>
                  <td
                    className="py-3 px-3 font-mono text-sm"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {trader.winRate}%
                  </td>
                  <td className="py-3 px-3">
                    <span className="flex items-center gap-1 font-mono text-sm" style={{ color: "var(--color-text-secondary)" }}>
                      <Users size={12} />
                      {trader.followers}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <RiskBadge score={trader.riskScore} />
                  </td>
                  <td className="py-3 px-3">
                    <button
                      disabled
                      className="text-xs font-medium px-3 py-1.5 rounded-lg opacity-50 cursor-not-allowed"
                      style={{ backgroundColor: "var(--color-accent)", color: "#fff" }}
                    >
                      Follow
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Info Card */}
      <div
        className="glass p-5"
        style={{ borderLeft: "3px solid var(--color-accent)" }}
      >
        <div className="flex items-start gap-3">
          <Info size={18} className="mt-0.5 shrink-0" style={{ color: "var(--color-accent)" }} />
          <div>
            <h3
              className="text-sm font-bold mb-2"
              style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
            >
              How Copy Trading Works
            </h3>
            <ul className="space-y-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
              <li className="flex items-start gap-2">
                <Shield size={14} className="mt-0.5 shrink-0" style={{ color: "var(--color-profit)" }} />
                Follow verified traders with audited track records
              </li>
              <li className="flex items-start gap-2">
                <Shield size={14} className="mt-0.5 shrink-0" style={{ color: "var(--color-profit)" }} />
                Your account mirrors their positions proportionally to your balance
              </li>
              <li className="flex items-start gap-2">
                <Shield size={14} className="mt-0.5 shrink-0" style={{ color: "var(--color-profit)" }} />
                20% performance fee on profits only — no fee if no gains
              </li>
              <li className="flex items-start gap-2">
                <Shield size={14} className="mt-0.5 shrink-0" style={{ color: "var(--color-profit)" }} />
                Unfollow at any time — open positions remain until closed
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Banner */}
      <div
        className="glass p-5 text-center"
        style={{ borderLeft: "3px solid var(--color-warning)" }}
      >
        <span
          className="text-xs font-bold uppercase tracking-wider"
          style={{ color: "var(--color-warning)" }}
        >
          Coming in Phase 3
        </span>
        <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
          Copy trading will be available after the marketplace launch
        </p>
      </div>
    </div>
  );
}
