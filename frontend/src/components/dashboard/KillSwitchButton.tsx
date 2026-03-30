"use client";
import { useState } from "react";
import { AlertTriangle, ShieldOff } from "lucide-react";

type KillSwitchState = "idle" | "confirming" | "loading" | "success" | "error";

const CONFIRMATION_PHRASE = "HALT TRADING";

export default function KillSwitchButton() {
  const [state, setState] = useState<KillSwitchState>("idle");
  const [input, setInput] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const isConfirmed = input === CONFIRMATION_PHRASE;

  const handleActivate = () => {
    setState("confirming");
    setInput("");
    setErrorMessage("");
  };

  const handleCancel = () => {
    setState("idle");
    setInput("");
    setErrorMessage("");
  };

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
      <div className="glass p-4" style={{ borderColor: "var(--color-loss)", borderWidth: 1 }} role="alert" aria-live="assertive">
        <div className="flex items-center gap-2">
          <ShieldOff className="w-5 h-5 text-loss" />
          <span className="text-sm font-bold text-loss">Trading Halted</span>
        </div>
        <p className="text-xs text-secondary mt-2">
          All open positions preserved. System will not open new trades.
        </p>
        <button
          onClick={() => { setState("idle"); setInput(""); }}
          className="mt-3 text-xs text-accent hover:underline"
        >
          Reset
        </button>
      </div>
    );
  }

  if (state === "idle") {
    return (
      <div className="glass p-4">
        <div className="flex items-center gap-2 mb-3">
          <div
            className="w-6 h-6 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "var(--color-loss-dim)" }}
          >
            <ShieldOff size={12} style={{ color: "var(--color-loss)" }} />
          </div>
          <p className="text-label" style={{ color: "var(--color-text-secondary)" }}>Emergency</p>
        </div>
        <button
          onClick={handleActivate}
          className="w-full py-2.5 px-4 bg-loss-dim border border-loss/30 rounded-lg text-sm font-bold text-loss hover:bg-loss/20 transition-colors flex items-center justify-center gap-2"
        >
          <AlertTriangle size={14} />
          Kill Switch
        </button>
      </div>
    );
  }

  // confirming | loading | error states
  return (
    <div className="glass p-4" style={{ borderColor: "var(--color-loss)", borderWidth: 1 }}>
      <p className="text-label text-loss mb-2">Confirm Emergency Halt</p>
      <p className="text-xs text-secondary mb-3">
        This will immediately halt all trading activity. Open positions will be preserved.
      </p>
      <div className="space-y-3">
        <div>
          <label htmlFor="kill-confirm" className="text-[10px] text-tertiary block mb-1">
            Type <span className="font-mono font-bold text-loss">{CONFIRMATION_PHRASE}</span> to confirm
          </label>
          <input
            id="kill-confirm"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={state === "loading"}
            className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm font-mono text-primary placeholder:text-tertiary focus:outline-none focus:border-loss/50"
            placeholder={CONFIRMATION_PHRASE}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        {state === "error" && errorMessage && (
          <p className="text-xs text-loss" role="alert">{errorMessage}</p>
        )}
        <div className="flex gap-2">
          <button
            onClick={handleCancel}
            disabled={state === "loading"}
            className="flex-1 py-2 px-3 bg-elevated border border-border rounded-lg text-xs text-secondary hover:text-primary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isConfirmed || state === "loading"}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-colors ${
              isConfirmed && state !== "loading"
                ? "bg-loss text-white hover:bg-loss/80"
                : "bg-elevated text-tertiary border border-border cursor-not-allowed"
            }`}
          >
            {state === "loading" ? (
              <span className="flex items-center justify-center gap-1.5">
                <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Halting...
              </span>
            ) : (
              "Confirm Halt"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
