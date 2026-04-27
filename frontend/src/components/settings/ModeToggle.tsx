"use client";

import { useState } from "react";
import { AlertTriangle, Info, Lock } from "lucide-react";

interface ModeToggleProps {
  mode: "PAPER" | "LIVE";
  onToggle: (mode: "PAPER" | "LIVE") => void;
  disabled?: boolean;
  /** TRADING_MODE env var on Railway. Restart-only. */
  envMode?: "PAPER" | "LIVE";
  /** What the engine actually executes against. LIVE iff envMode AND mode are both LIVE. */
  effectiveMode?: "PAPER" | "LIVE";
  /**
   * Backend-side hard lock (FORCE_PAPER_MODE env). When true, the LIVE
   * button is hidden, the toggle becomes non-interactive, and a lock
   * banner explains that no real-broker order can fire regardless of UI
   * action. Use during demo / practice weeks.
   */
  forcePaperLockdown?: boolean;
}

const ARM_PHRASE = "START LIVE TRADING";

export default function ModeToggle({
  mode,
  onToggle,
  disabled = false,
  envMode,
  effectiveMode,
  forcePaperLockdown = false,
}: ModeToggleProps) {
  // Live LIVE requires BOTH the env var AND the user's dashboard selection
  // to say LIVE. If the env is PAPER, the LIVE button is locked — selecting
  // it persists user intent but won't actually execute live until env flips.
  const liveLocked = envMode === "PAPER";
  const modesDisagree = effectiveMode !== undefined && effectiveMode !== mode;
  const [phase, setPhase] = useState<"idle" | "arming">("idle");
  const [input, setInput] = useState("");
  const [riskAck, setRiskAck] = useState(false);

  const inputMatches = input === ARM_PHRASE;
  const canArm = inputMatches && riskAck && !disabled && !forcePaperLockdown;

  function handlePaperSelect() {
    // PAPER is the safe default — halting is always immediate, no ceremony.
    if (disabled) return;
    if (mode === "PAPER") return;
    onToggle("PAPER");
    setPhase("idle");
    setInput("");
    setRiskAck(false);
  }

  function handleLiveSelect() {
    if (disabled || mode === "LIVE" || forcePaperLockdown) return;
    setPhase("arming");
    setInput("");
    setRiskAck(false);
  }

  function handleCancel() {
    setPhase("idle");
    setInput("");
    setRiskAck(false);
  }

  function handleConfirmArm() {
    if (!canArm) return;
    onToggle("LIVE");
    setPhase("idle");
    setInput("");
    setRiskAck(false);
  }

  return (
    <div className="glass p-5">
      <h2 className="text-heading text-primary mb-4">Trading Mode</h2>

      {effectiveMode !== undefined && envMode !== undefined && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-elevated border border-border flex items-center gap-2 text-xs">
          <Info size={14} className="text-tertiary shrink-0" />
          <span className="text-tertiary">Engine env:</span>
          <span className={`font-mono font-bold ${envMode === "LIVE" ? "text-profit" : "text-warning"}`}>
            {envMode}
          </span>
          <span className="text-tertiary">·</span>
          <span className="text-tertiary">Effective:</span>
          <span className={`font-mono font-bold ${effectiveMode === "LIVE" ? "text-profit" : "text-warning"}`}>
            {effectiveMode}
          </span>
          {modesDisagree && (
            <span className="ml-auto text-loss font-bold">selection ≠ effective</span>
          )}
        </div>
      )}

      {forcePaperLockdown && (
        <div
          className="mb-3 px-3 py-2 rounded-lg border border-warning bg-warning-dim text-xs text-warning flex items-start gap-2"
          role="status"
          aria-live="polite"
        >
          <Lock size={14} className="shrink-0 mt-0.5" />
          <span>
            <span className="font-bold">Demo Week — Paper Lock active.</span>{" "}
            <span className="font-mono mx-1">FORCE_PAPER_MODE</span>is set on
            the engine. New orders are simulated by PaperExecutor — no live
            broker entry will fire regardless of toggle state. (Existing
            open positions and manual close actions still talk to the
            broker; OANDA endpoint is currently <span className="font-mono">practice</span>.)
          </span>
        </div>
      )}

      {!forcePaperLockdown && liveLocked && (
        <div className="mb-3 px-3 py-2 rounded-lg border border-warning bg-warning-dim text-xs text-warning flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>
            LIVE selection saves your intent but cannot execute real trades — Railway
            <span className="font-mono mx-1">TRADING_MODE</span>is currently <span className="font-mono">PAPER</span>.
          </span>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handlePaperSelect}
          disabled={disabled}
          className={`flex-1 py-3 rounded-lg border text-sm font-bold transition-colors ${
            mode === "PAPER" || forcePaperLockdown
              ? "bg-warning-dim border-warning text-warning"
              : "bg-elevated border-border text-secondary"
          } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          aria-pressed={mode === "PAPER" || forcePaperLockdown}
        >
          PAPER
        </button>

        {!forcePaperLockdown && (
          <button
            onClick={handleLiveSelect}
            disabled={disabled || phase === "arming"}
            className={`flex-1 py-3 rounded-lg border text-sm font-bold transition-colors ${
              mode === "LIVE"
                ? "bg-profit-dim border-profit text-profit"
                : "bg-elevated border-border text-secondary"
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            aria-pressed={mode === "LIVE"}
          >
            LIVE
          </button>
        )}
      </div>

      {phase === "arming" && (
        <div
          className="mt-4 p-4 rounded-lg border"
          style={{ borderColor: "var(--color-loss)", backgroundColor: "var(--color-loss-dim)" }}
          role="alertdialog"
          aria-labelledby="arm-live-title"
        >
          <div className="flex items-start gap-2 mb-3">
            <AlertTriangle size={16} className="text-loss shrink-0 mt-0.5" />
            <div>
              <p id="arm-live-title" className="text-sm font-bold text-loss mb-1">
                Arming Live Trading
              </p>
              <p className="text-xs text-secondary">
                The engine will execute real trades with real capital on your next
                signal scan. Halting is always available via the Kill Switch.
              </p>
            </div>
          </div>

          <label className="flex items-start gap-2 mb-3 cursor-pointer">
            <input
              type="checkbox"
              checked={riskAck}
              onChange={(e) => setRiskAck(e.target.checked)}
              className="mt-0.5 accent-brand"
              aria-describedby="risk-ack-copy"
            />
            <span id="risk-ack-copy" className="text-xs text-secondary">
              I understand that forex trading involves risk of loss and that I may
              lose more than my initial deposit. I have completed all go/no-go
              checks.
            </span>
          </label>

          <div className="mb-3">
            <label htmlFor="arm-confirm" className="text-[10px] text-tertiary block mb-1">
              Type <span className="font-mono font-bold text-loss">{ARM_PHRASE}</span> to confirm
            </label>
            <input
              id="arm-confirm"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-sm font-mono text-primary placeholder:text-tertiary focus:outline-none focus:border-loss/50"
              placeholder={ARM_PHRASE}
              autoComplete="off"
              spellCheck={false}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              className="flex-1 py-2 px-3 bg-elevated border border-border rounded-lg text-xs text-secondary hover:text-primary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmArm}
              disabled={!canArm}
              className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-colors ${
                canArm
                  ? "bg-loss text-white hover:bg-loss/80"
                  : "bg-elevated text-tertiary border border-border cursor-not-allowed"
              }`}
            >
              Arm Live Trading
            </button>
          </div>
        </div>
      )}

      {phase === "idle" && mode === "LIVE" && !forcePaperLockdown && (
        <div className="flex items-start gap-2 mt-3">
          <AlertTriangle size={14} className="text-loss shrink-0 mt-0.5" />
          <p className="text-xs text-loss">
            Live trading is armed. Real capital at risk. Use the Kill Switch to
            halt immediately.
          </p>
        </div>
      )}
    </div>
  );
}
