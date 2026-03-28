"use client";
import { useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, ShieldOff } from "lucide-react";

type KillSwitchState = "idle" | "confirming" | "loading" | "success" | "error";
const CONFIRMATION_PHRASE = "HALT TRADING";

export default function KillSwitchButton() {
  const [state, setState] = useState<KillSwitchState>("idle");
  const [input, setInput] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const isConfirmed = input === CONFIRMATION_PHRASE;

  const handleActivate = () => { setState("confirming"); setInput(""); setErrorMessage(""); };
  const handleCancel = () => { setState("idle"); setInput(""); setErrorMessage(""); };

  const handleConfirm = async () => {
    if (!isConfirmed) return;
    setState("loading");
    try {
      const res = await fetch("/api/control/kill-switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "HALT" }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setState("success");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      setState("error");
    }
  };

  if (state === "success") {
    return (
      <div
        className="p-4"
        style={{
          background: "rgba(255, 77, 106, 0.06)",
          border: "1px solid rgba(255, 77, 106, 0.3)",
          borderRadius: "var(--card-radius)",
        }}
        role="alert"
        aria-live="assertive"
      >
        <div className="flex items-center gap-2 mb-2">
          <ShieldOff size={16} style={{ color: "var(--color-loss)" }} />
          <span className="text-sm font-bold" style={{ color: "var(--color-loss)" }}>Trading Halted</span>
        </div>
        <p className="text-[11px] mb-3" style={{ color: "var(--color-text-secondary)" }}>
          All open positions preserved. System will not open new trades.
        </p>
        <button
          onClick={() => { setState("idle"); setInput(""); }}
          className="text-[11px] font-medium"
          style={{ color: "var(--color-accent)" }}
        >
          Reset
        </button>
      </div>
    );
  }

  if (state === "idle") {
    return (
      <div className="glass-muted p-4">
        <p className="text-label mb-2.5" style={{ color: "var(--color-text-tertiary)" }}>Emergency</p>
        <motion.button
          onClick={handleActivate}
          className="w-full py-2.5 px-4 rounded-lg text-[12px] font-bold tracking-wide transition-colors"
          style={{
            background: "rgba(255, 77, 106, 0.08)",
            border: "1px solid rgba(255, 77, 106, 0.25)",
            color: "var(--color-loss)",
          }}
          whileHover={{
            backgroundColor: "rgba(255, 77, 106, 0.15)",
            borderColor: "rgba(255, 77, 106, 0.4)",
          }}
          whileTap={{ scale: 0.98 }}
        >
          <div className="flex items-center justify-center gap-2">
            <AlertTriangle size={14} />
            Kill Switch
          </div>
        </motion.button>
      </div>
    );
  }

  return (
    <div
      className="p-4"
      style={{
        background: "rgba(255, 77, 106, 0.04)",
        border: "1px solid rgba(255, 77, 106, 0.25)",
        borderRadius: "var(--card-radius)",
      }}
    >
      <p className="text-label mb-2" style={{ color: "var(--color-loss)" }}>Confirm Emergency Halt</p>
      <p className="text-[11px] mb-3" style={{ color: "var(--color-text-secondary)" }}>
        This will immediately halt all trading. Open positions will be preserved.
      </p>
      <div className="space-y-3">
        <div>
          <label htmlFor="kill-confirm" className="text-[10px] block mb-1" style={{ color: "var(--color-text-tertiary)" }}>
            Type <span className="font-mono font-bold" style={{ color: "var(--color-loss)" }}>{CONFIRMATION_PHRASE}</span> to confirm
          </label>
          <input
            id="kill-confirm"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={state === "loading"}
            className="w-full px-3 py-2 text-sm font-mono rounded-lg focus:outline-none"
            style={{
              background: "var(--color-bg-input)",
              border: "1px solid rgba(255, 77, 106, 0.2)",
              color: "var(--color-text-primary)",
            }}
            placeholder={CONFIRMATION_PHRASE}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        {state === "error" && errorMessage && (
          <p className="text-[11px]" style={{ color: "var(--color-loss)" }} role="alert">{errorMessage}</p>
        )}
        <div className="flex gap-2">
          <button
            onClick={handleCancel}
            disabled={state === "loading"}
            className="flex-1 py-2 px-3 rounded-lg text-[11px] transition-colors disabled:opacity-50"
            style={{
              background: "var(--color-bg-elevated)",
              border: "1px solid var(--color-border)",
              color: "var(--color-text-secondary)",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isConfirmed || state === "loading"}
            className={`flex-1 py-2 px-3 rounded-lg text-[11px] font-bold transition-all ${
              isConfirmed && state !== "loading"
                ? "text-white"
                : "cursor-not-allowed"
            }`}
            style={{
              background: isConfirmed && state !== "loading"
                ? "var(--color-loss)"
                : "var(--color-bg-elevated)",
              color: isConfirmed && state !== "loading"
                ? "#fff"
                : "var(--color-text-tertiary)",
              border: isConfirmed && state !== "loading"
                ? "1px solid var(--color-loss)"
                : "1px solid var(--color-border)",
            }}
          >
            {state === "loading" ? (
              <span className="flex items-center justify-center gap-1.5">
                <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Halting...
              </span>
            ) : "Confirm Halt"}
          </button>
        </div>
      </div>
    </div>
  );
}
