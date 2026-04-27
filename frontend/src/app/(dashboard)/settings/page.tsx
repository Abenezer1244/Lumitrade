"use client";

import { useState, useEffect, useCallback } from "react";
import TradingSettings from "@/components/settings/TradingSettings";
import ModeToggle from "@/components/settings/ModeToggle";
import type { TradingSettingsData, GuardrailsData } from "@/components/settings/TradingSettings";
import { useToast } from "@/components/ui/Toast";

const DEFAULT_SETTINGS: TradingSettingsData = {
  riskPct: 0.5,
  maxPositions: 3,
  maxPerPair: 1,
  confidence: 65,
  scanInterval: 15,
};

const DEFAULT_GUARDRAILS: GuardrailsData = {
  maxPositionUnits: 500_000,
  dailyLossLimitPct: 5.0,
  weeklyLossLimitPct: 10.0,
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<TradingSettingsData>(DEFAULT_SETTINGS);
  const [guardrails, setGuardrails] = useState<GuardrailsData>(DEFAULT_GUARDRAILS);
  const [mode, setMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [envMode, setEnvMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [forcePaperLockdown, setForcePaperLockdown] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    let cancelled = false;
    async function fetchSettings() {
      try {
        const res = await fetch("/api/settings");
        if (!res.ok) throw new Error("Failed to fetch settings");
        const data = await res.json();
        if (cancelled) return;
        setSettings({
          riskPct: data.riskPct ?? DEFAULT_SETTINGS.riskPct,
          maxPositions: data.maxPositions ?? DEFAULT_SETTINGS.maxPositions,
          maxPerPair: data.maxPerPair ?? DEFAULT_SETTINGS.maxPerPair,
          confidence: data.confidence ?? DEFAULT_SETTINGS.confidence,
          scanInterval: data.scanInterval ?? DEFAULT_SETTINGS.scanInterval,
        });
        setMode(data.mode ?? "PAPER");
        setEnvMode(data.env_mode ?? "PAPER");
        setForcePaperLockdown(Boolean(data.force_paper_mode));
        if (data.guardrails) {
          setGuardrails({
            maxPositionUnits: data.guardrails.maxPositionUnits ?? DEFAULT_GUARDRAILS.maxPositionUnits,
            dailyLossLimitPct: data.guardrails.dailyLossLimitPct ?? DEFAULT_GUARDRAILS.dailyLossLimitPct,
            weeklyLossLimitPct: data.guardrails.weeklyLossLimitPct ?? DEFAULT_GUARDRAILS.weeklyLossLimitPct,
          });
        }
      } catch {
        // Use defaults on failure
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }
    fetchSettings();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...settings, mode }),
      });
      if (!res.ok) throw new Error("Save failed");
      toast("Settings saved", "success");
    } catch {
      toast("Failed to save settings", "error");
    } finally {
      setSaving(false);
    }
  }, [settings, mode, toast]);

  const handleModeToggle = useCallback(async (newMode: "PAPER" | "LIVE") => {
    setMode(newMode);
    setSaving(true);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...settings, mode: newMode }),
      });
      if (!res.ok) throw new Error("Save failed");
      toast(`Trading mode set to ${newMode}`, "success");
    } catch {
      toast("Failed to save mode change", "error");
      setMode(newMode === "LIVE" ? "PAPER" : "LIVE");
    } finally {
      setSaving(false);
    }
  }, [settings, toast]);

  if (!loaded) {
    return <div className="animate-pulse h-96 glass" />;
  }

  return (
    <div>
      <div className="space-y-6 max-w-2xl">
        <ModeToggle
          mode={mode}
          onToggle={handleModeToggle}
          envMode={envMode}
          effectiveMode={
            forcePaperLockdown
              ? "PAPER"
              : envMode === "LIVE" && mode === "LIVE"
                ? "LIVE"
                : "PAPER"
          }
          forcePaperLockdown={forcePaperLockdown}
        />
        <TradingSettings
          settings={settings}
          guardrails={guardrails}
          onChange={setSettings}
          onSave={handleSave}
          saving={saving}
        />
      </div>
    </div>
  );
}
