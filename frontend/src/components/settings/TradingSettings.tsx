"use client";

import { SlidersHorizontal, ShieldCheck } from "lucide-react";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

export interface TradingSettingsData {
  riskPct: number;
  maxPositions: number;
  maxPerPair: number;
  confidence: number;
  scanInterval: number;
}

export interface GuardrailsData {
  maxPositionUnits: number;
  dailyLossLimitPct: number;
  weeklyLossLimitPct: number;
}

interface TradingSettingsProps {
  settings: TradingSettingsData;
  guardrails: GuardrailsData;
  onChange: (settings: TradingSettingsData) => void;
  onSave: () => void;
  saving: boolean;
}

interface SliderConfig {
  key: keyof TradingSettingsData;
  label: string;
  description: string;
  recommended: string;
  tradeoff: string;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
}

const SLIDERS: SliderConfig[] = [
  {
    key: "riskPct",
    label: "Max Risk Per Trade",
    description: "Percent of account equity risked if the stop-loss is hit.",
    recommended: "0.5–1%",
    tradeoff: "Above 2%, a 5-trade losing streak can wipe ~10% of the account.",
    min: 0.25,
    max: 2,
    step: 0.25,
    format: (v) => `${v.toFixed(2)}%`,
  },
  {
    key: "maxPositions",
    label: "Max Open Positions",
    description: "Total trades open at once across all currency pairs.",
    recommended: "3–5",
    tradeoff: "Higher = more simultaneous exposure during news shocks.",
    min: 1,
    max: 100,
    step: 1,
    format: (v) => `${v}`,
  },
  {
    key: "maxPerPair",
    label: "Max Positions Per Pair",
    description: "How many trades the AI can stack on the same pair.",
    recommended: "1",
    tradeoff: "Stacking multiplies your loss if the pair moves against you.",
    min: 1,
    max: 10,
    step: 1,
    format: (v) => `${v}`,
  },
  {
    key: "scanInterval",
    label: "Scan Interval",
    description: "How often the AI re-evaluates each pair for new signals.",
    recommended: "15 min",
    tradeoff: "Shorter = more broker API load and more false-start trades.",
    min: 5,
    max: 60,
    step: 5,
    format: (v) => `${v} min`,
  },
  {
    key: "confidence",
    label: "Min Confidence Threshold",
    description: "AI confidence score (0–100) required before placing a trade.",
    recommended: "65–70",
    tradeoff: "Lower = more trades but weaker setups and lower win rate.",
    min: 50,
    max: 90,
    step: 5,
    format: (v) => `${v}%`,
  },
];

interface GuardrailConfig {
  label: string;
  value: string;
  description: string;
}

function getGuardrailItems(g: GuardrailsData): GuardrailConfig[] {
  return [
    {
      label: "Max Position Size",
      value: `${(g.maxPositionUnits / 1000).toFixed(0)}K units`,
      description: "Hard cap per trade — prevents oversized positions",
    },
    {
      label: "Daily Loss Limit",
      value: `${g.dailyLossLimitPct.toFixed(1)}%`,
      description: "Engine halts if daily losses exceed this",
    },
    {
      label: "Weekly Loss Limit",
      value: `${g.weeklyLossLimitPct.toFixed(1)}%`,
      description: "Engine halts if weekly losses exceed this",
    },
  ];
}

export default function TradingSettings({
  settings,
  guardrails,
  onChange,
  onSave,
  saving,
}: TradingSettingsProps) {
  function handleSliderChange(key: keyof TradingSettingsData, raw: string) {
    const value = key === "maxPositions" || key === "maxPerPair" || key === "scanInterval"
      ? parseInt(raw, 10)
      : parseFloat(raw);
    onChange({ ...settings, [key]: value });
  }

  const guardrailItems = getGuardrailItems(guardrails);

  return (
    <div className="space-y-6">
      {/* User-adjustable settings */}
      <div className="glass p-5">
        <div className="flex items-center gap-2 mb-4">
          <SlidersHorizontal size={18} className="text-brand" />
          <h2 className="text-heading text-primary">Trading Parameters</h2>
        </div>
        <p className="text-xs text-tertiary mb-5">
          Adjust these to control how aggressively the AI trades. Changes take effect on the next signal scan.
        </p>

        <div className="space-y-6">
          {SLIDERS.map((slider) => (
            <div key={slider.key}>
              <div className="flex items-center justify-between mb-1">
                <label className="text-label text-secondary">{slider.label}</label>
                <span className="font-mono text-sm text-primary font-bold">
                  {slider.format(settings[slider.key])}
                </span>
              </div>
              <p className="text-xs text-tertiary mb-2">{slider.description}</p>
              <input
                type="range"
                min={slider.min}
                max={slider.max}
                step={slider.step}
                value={settings[slider.key]}
                onChange={(e) => handleSliderChange(slider.key, e.target.value)}
                className="w-full cursor-pointer accent-brand"
                aria-label={slider.label}
                aria-describedby={`${slider.key}-guidance`}
                aria-valuemin={slider.min}
                aria-valuemax={slider.max}
                aria-valuenow={settings[slider.key]}
                aria-valuetext={slider.format(settings[slider.key])}
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-tertiary">
                  {slider.format(slider.min)}
                </span>
                <span className="text-xs text-tertiary">
                  {slider.format(slider.max)}
                </span>
              </div>
              <p
                id={`${slider.key}-guidance`}
                className="text-[11px] mt-2 leading-snug"
              >
                <span className="font-semibold" style={{ color: "var(--color-brand)" }}>
                  Recommended {slider.recommended}.
                </span>{" "}
                <span style={{ color: "var(--color-text-tertiary)" }}>
                  {slider.tradeoff}
                </span>
              </p>
            </div>
          ))}

          <button
            onClick={onSave}
            disabled={saving}
            className="flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold transition-all disabled:opacity-60 disabled:cursor-not-allowed active:scale-[0.98]"
            style={{ backgroundColor: "var(--color-brand)", color: "var(--color-bg-primary)" }}
          >
            {saving && <LoadingSpinner size="sm" />}
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      {/* Guardrails — read-only */}
      <div className="glass p-5 border border-border/50">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck size={18} className="text-warning" />
          <h2 className="text-heading text-primary">Safety Guardrails</h2>
        </div>
        <p className="text-xs text-tertiary mb-4">
          These limits protect against catastrophic losses. They can only be changed via environment variables (requires redeploy) to prevent impulsive changes during losing streaks.
        </p>

        <div className="space-y-3">
          {guardrailItems.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between py-3 px-4 rounded-lg"
              style={{ backgroundColor: "var(--color-bg-elevated)" }}
            >
              <div>
                <span className="text-sm text-secondary">{item.label}</span>
                <p className="text-xs text-tertiary mt-0.5">{item.description}</p>
              </div>
              <span className="font-mono text-sm text-warning font-bold whitespace-nowrap ml-4">
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
