"use client";

import { Key, Copy, Check, Lock, Zap, Globe, Shield, Trash2, Plus, AlertCircle } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

interface Endpoint {
  method: string;
  path: string;
  description: string;
}

const ENDPOINTS: Endpoint[] = [
  { method: "GET", path: "/api/v1/trades", description: "Closed trades with P&L, pair, direction, and exit reason" },
  { method: "GET", path: "/api/v1/signals", description: "Generated trading signals with confidence scores" },
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

interface ApiKeyRow {
  id: string;
  label: string;
  key_preview: string;
  scopes: string[];
  rate_limit: number;
  active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export default function ApiAccessPage() {
  const [copied, setCopied] = useState<string | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [showGenerate, setShowGenerate] = useState(false);
  const [newKeyFull, setNewKeyFull] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch("/api/api-keys");
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || []);
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  async function handleGenerate() {
    setError("");
    try {
      const res = await fetch("/api/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: newKeyLabel || "Default" }),
      });
      if (!res.ok) { setError("Failed to generate key"); return; }
      const data = await res.json();
      setNewKeyFull(data.key);
      setShowGenerate(false);
      setNewKeyLabel("");
      fetchKeys();
    } catch { setError("Failed to generate key"); }
  }

  async function handleRevoke(id: string) {
    try {
      await fetch("/api/api-keys", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      fetchKeys();
    } catch { /* ignore */ }
  }

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
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
  https://api.lumitrade.com/api/v1/trades`}</code>
          </pre>
        </div>
        <p className="text-xs mt-3" style={{ color: "var(--color-text-tertiary)" }}>
          Never share your API key. Rotate keys immediately if compromised.
        </p>
      </div>

      {/* Section 3: API Keys — REAL key management */}
      <div className="glass p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Key size={16} style={{ color: "var(--color-accent)" }} />
            <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--color-text-primary)" }}>
              API Keys
            </h2>
          </div>
          <button
            onClick={() => setShowGenerate(!showGenerate)}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
            style={{ backgroundColor: "var(--color-accent)", color: "#fff" }}
          >
            <Plus size={12} /> Generate New Key
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg mb-4" style={{ backgroundColor: "var(--color-loss-dim)", color: "var(--color-loss)" }}>
            <AlertCircle size={14} /> <span className="text-xs">{error}</span>
          </div>
        )}

        {/* New key full display — shown once after generation */}
        {newKeyFull && (
          <div className="p-4 rounded-lg mb-4" style={{ backgroundColor: "var(--color-profit-dim)", border: "1px solid var(--color-profit)" }}>
            <p className="text-xs font-semibold mb-2" style={{ color: "var(--color-profit)" }}>
              Copy this key now — it will not be shown again
            </p>
            <div className="flex items-center gap-2">
              <code className="font-mono text-sm flex-1 break-all" style={{ color: "var(--color-text-primary)" }}>{newKeyFull}</code>
              <button
                onClick={() => handleCopy(newKeyFull)}
                className="shrink-0 px-3 py-1.5 rounded text-xs"
                style={{ backgroundColor: "var(--color-profit)", color: "#fff" }}
              >
                {copied === newKeyFull ? "Copied" : "Copy"}
              </button>
            </div>
            <button onClick={() => setNewKeyFull(null)} className="text-xs mt-2 underline" style={{ color: "var(--color-text-tertiary)" }}>
              Dismiss
            </button>
          </div>
        )}

        {/* Generate form */}
        {showGenerate && (
          <div className="p-4 rounded-lg mb-4 flex items-center gap-3" style={{ backgroundColor: "var(--color-bg-primary)", border: "1px solid var(--color-border)" }}>
            <input
              type="text"
              placeholder="Key label (e.g. MyBot)"
              value={newKeyLabel}
              onChange={(e) => setNewKeyLabel(e.target.value)}
              className="flex-1 px-3 py-2 rounded text-sm bg-transparent"
              style={{ color: "var(--color-text-primary)", border: "1px solid var(--color-border)" }}
            />
            <button onClick={handleGenerate} className="px-4 py-2 rounded text-xs font-medium" style={{ backgroundColor: "var(--color-accent)", color: "#fff" }}>
              Create
            </button>
          </div>
        )}

        {/* Key list */}
        {loading ? (
          <div className="animate-pulse h-16 rounded-lg" style={{ backgroundColor: "var(--color-bg-primary)" }} />
        ) : keys.length === 0 ? (
          <p className="text-sm text-center py-6" style={{ color: "var(--color-text-tertiary)" }}>
            No API keys yet. Generate one to get started.
          </p>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div
                key={k.id}
                className="rounded-lg p-4 flex items-center justify-between gap-4"
                style={{ backgroundColor: "var(--color-bg-primary)", border: "1px solid var(--color-border)" }}
              >
                <div className="flex items-center gap-4 min-w-0">
                  <span className="text-sm font-medium shrink-0" style={{ color: "var(--color-text-primary)" }}>
                    {k.label}
                  </span>
                  <span className="font-mono text-sm truncate" style={{ color: "var(--color-text-secondary)" }}>
                    {k.key_preview}
                  </span>
                  <span className="text-xs shrink-0" style={{ color: "var(--color-text-tertiary)" }}>
                    {new Date(k.created_at).toLocaleDateString()}
                  </span>
                  {k.last_used_at && (
                    <span className="text-xs shrink-0" style={{ color: "var(--color-text-tertiary)" }}>
                      Last used: {new Date(k.last_used_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleRevoke(k.id)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors"
                  style={{ color: "var(--color-loss)" }}
                >
                  <Trash2 size={12} /> Revoke
                </button>
              </div>
            ))}
          </div>
        )}
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
