"use client";

import { Key, Copy, Check, Lock, Zap, Globe, Shield } from "lucide-react";
import { useState } from "react";

interface Endpoint {
  method: string;
  path: string;
  description: string;
}

const ENDPOINTS: Endpoint[] = [
  { method: "GET", path: "/v1/signals/latest", description: "Get most recent trading signals" },
  { method: "GET", path: "/v1/trades/recent", description: "Recent trades with P&L" },
  { method: "GET", path: "/v1/analytics", description: "Account analytics and performance" },
  { method: "WSS", path: "/v1/signals/stream", description: "Real-time signal WebSocket stream" },
  { method: "POST", path: "/v1/webhooks", description: "Register webhook endpoint" },
];

function MethodBadge({ method }: { method: string }) {
  const colorMap: Record<string, string> = {
    GET: "var(--color-profit)",
    POST: "var(--color-accent)",
    WSS: "var(--color-warning)",
  };
  const bg = colorMap[method] ?? "var(--color-text-tertiary)";

  return (
    <span
      className="inline-block text-[10px] font-mono font-bold px-2 py-0.5 rounded"
      style={{ backgroundColor: `${bg}20`, color: bg }}
    >
      {method}
    </span>
  );
}

export default function ApiAccessPage() {
  const [copied, setCopied] = useState(false);
  const sampleKey = "sk_live_****************************7f2a";

  function handleCopy() {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: "var(--color-accent)", opacity: 0.15 }}
        >
          <Key size={20} style={{ color: "var(--color-accent)" }} />
        </div>
        <div>
          <h1
            className="text-xl font-bold"
            style={{ color: "var(--color-text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Public API
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Programmatic access to Lumitrade signals, trades, and analytics
          </p>
        </div>
      </div>

      {/* Section 1: API Endpoints */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <Globe size={16} style={{ color: "var(--color-accent)" }} />
          <h2
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
          >
            API Endpoints
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                <th
                  className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider"
                  style={{ color: "var(--color-text-tertiary)" }}
                >
                  Method
                </th>
                <th
                  className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider"
                  style={{ color: "var(--color-text-tertiary)" }}
                >
                  Endpoint
                </th>
                <th
                  className="text-left py-2 px-3 text-xs font-bold uppercase tracking-wider"
                  style={{ color: "var(--color-text-tertiary)" }}
                >
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((ep) => (
                <tr
                  key={ep.path}
                  className="transition-colors"
                  style={{ borderBottom: "1px solid var(--color-border)" }}
                >
                  <td className="py-3 px-3">
                    <MethodBadge method={ep.method} />
                  </td>
                  <td
                    className="py-3 px-3 font-mono text-sm"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    {ep.path}
                  </td>
                  <td className="py-3 px-3" style={{ color: "var(--color-text-secondary)" }}>
                    {ep.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Authentication */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <Lock size={16} style={{ color: "var(--color-accent)" }} />
          <h2
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
          >
            Authentication
          </h2>
        </div>
        <p className="text-sm mb-4" style={{ color: "var(--color-text-secondary)" }}>
          All API requests require a Bearer token in the Authorization header.
          Include your API key with every request.
        </p>
        <div
          className="rounded-lg p-4 overflow-x-auto"
          style={{ backgroundColor: "var(--color-bg-primary)", border: "1px solid var(--color-border)" }}
        >
          <pre
            className="text-sm leading-relaxed"
            style={{ color: "var(--color-text-primary)", fontFamily: "'JetBrains Mono', monospace" }}
          >
            <code>{`curl -H "Authorization: Bearer sk_live_..." \\
  https://api.lumitrade.com/v1/signals/latest`}</code>
          </pre>
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--color-text-tertiary)" }}>
          Never share your API key. Rotate keys immediately if compromised.
        </p>
      </div>

      {/* Section 3: API Keys */}
      <div className="glass p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Key size={16} style={{ color: "var(--color-accent)" }} />
            <h2
              className="text-sm font-bold uppercase tracking-wider"
              style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
            >
              API Keys
            </h2>
          </div>
          <div className="relative group">
            <button
              disabled
              className="text-xs font-medium px-3 py-1.5 rounded-lg opacity-50 cursor-not-allowed"
              style={{
                backgroundColor: "var(--color-accent)",
                color: "#fff",
              }}
            >
              Generate New Key
            </button>
            <div
              className="absolute bottom-full right-0 mb-2 px-2 py-1 rounded text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
              style={{
                backgroundColor: "var(--color-bg-elevated)",
                color: "var(--color-text-secondary)",
                border: "1px solid var(--color-border)",
              }}
            >
              Available in Phase 3
            </div>
          </div>
        </div>
        <div
          className="rounded-lg p-4 flex items-center justify-between gap-4"
          style={{
            backgroundColor: "var(--color-bg-primary)",
            border: "1px solid var(--color-border)",
          }}
        >
          <div className="flex items-center gap-4 min-w-0">
            <span
              className="text-sm font-medium shrink-0"
              style={{ color: "var(--color-text-primary)" }}
            >
              MyBot
            </span>
            <span
              className="font-mono text-sm truncate"
              style={{ color: "var(--color-text-secondary)" }}
            >
              {sampleKey}
            </span>
            <span
              className="text-xs shrink-0"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Created Mar 25, 2026
            </span>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors shrink-0"
            style={{
              backgroundColor: "var(--color-bg-elevated)",
              color: copied ? "var(--color-profit)" : "var(--color-text-secondary)",
              border: "1px solid var(--color-border)",
            }}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {/* Section 4: Webhooks */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={16} style={{ color: "var(--color-warning)" }} />
          <h2
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
          >
            Webhooks
          </h2>
        </div>
        <p className="text-sm mb-3" style={{ color: "var(--color-text-secondary)" }}>
          Receive real-time notifications when signals are generated or trades are executed.
          All webhook payloads are signed with HMAC-SHA256 for authenticity verification.
        </p>
        <div
          className="rounded-lg p-4 overflow-x-auto"
          style={{ backgroundColor: "var(--color-bg-primary)", border: "1px solid var(--color-border)" }}
        >
          <pre
            className="text-sm leading-relaxed"
            style={{ color: "var(--color-text-primary)", fontFamily: "'JetBrains Mono', monospace" }}
          >
            <code>{`// Verify webhook signature
const signature = req.headers["x-lumitrade-signature"];
const expected = crypto
  .createHmac("sha256", webhookSecret)
  .update(JSON.stringify(req.body))
  .digest("hex");

if (signature === expected) {
  // Payload is authentic
}`}</code>
          </pre>
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--color-text-tertiary)" }}>
          Webhook delivery includes automatic retries with exponential backoff (3 attempts).
        </p>
      </div>

      {/* Section 5: Rate Limits */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} style={{ color: "var(--color-accent)" }} />
          <h2
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: "var(--color-text-primary)", fontFamily: "'DM Sans', sans-serif" }}
          >
            Rate Limits
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            className="rounded-lg p-4"
            style={{
              backgroundColor: "var(--color-bg-primary)",
              border: "1px solid var(--color-border)",
            }}
          >
            <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "var(--color-text-tertiary)" }}>
              Standard
            </p>
            <p className="font-mono text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
              100 <span className="text-sm font-normal" style={{ color: "var(--color-text-secondary)" }}>req/min</span>
            </p>
          </div>
          <div
            className="rounded-lg p-4"
            style={{
              backgroundColor: "var(--color-bg-primary)",
              border: "1px solid var(--color-border)",
            }}
          >
            <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "var(--color-warning)" }}>
              Premium
            </p>
            <p className="font-mono text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
              1,000 <span className="text-sm font-normal" style={{ color: "var(--color-text-secondary)" }}>req/min</span>
            </p>
          </div>
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--color-text-tertiary)" }}>
          Rate limit headers are included in every response: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
        </p>
      </div>
    </div>
  );
}
