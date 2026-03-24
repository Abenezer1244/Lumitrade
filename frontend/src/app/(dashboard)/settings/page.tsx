"use client";

import { useState, useEffect, useCallback } from "react";
import TradingSettings from "@/components/settings/TradingSettings";
import ModeToggle from "@/components/settings/ModeToggle";
import type { TradingSettingsData } from "@/components/settings/TradingSettings";
import { useToast } from "@/components/ui/Toast";

const DEFAULT_SETTINGS: TradingSettingsData = {
  riskPct: 1.0,
  dailyLimit: 5.0,
  maxPositions: 3,
  confidence: 65,
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<TradingSettingsData>(DEFAULT_SETTINGS);
  const [mode, setMode] = useState<"PAPER" | "LIVE">("PAPER");
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
          dailyLimit: data.dailyLimit ?? DEFAULT_SETTINGS.dailyLimit,
          maxPositions: data.maxPositions ?? DEFAULT_SETTINGS.maxPositions,
          confidence: data.confidence ?? DEFAULT_SETTINGS.confidence,
        });
        setMode(data.mode ?? "PAPER");
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
  }, [settings, mode]);

  if (!loaded) {
    return <div className="animate-pulse h-96 glass" />;
  }

  return (
    <div>
      <div className="space-y-6 max-w-2xl">
        <ModeToggle mode={mode} onToggle={setMode} />
        <TradingSettings
          settings={settings}
          onChange={setSettings}
          onSave={handleSave}
          saving={saving}
        />
      </div>
    </div>
  );
}
