"use client";
import { useState } from "react";
export default function SettingsPage() {
  const [riskPct, setRiskPct] = useState(1.0);
  const [dailyLimit, setDailyLimit] = useState(5.0);
  const [maxPositions, setMaxPositions] = useState(3);
  const [confidence, setConfidence] = useState(65);
  return (
    <div>
      <h1 className="text-display text-primary mb-6">Settings</h1>
      <div className="bg-surface border border-border rounded-lg p-5 space-y-6 max-w-2xl">
        <div><p className="text-label text-tertiary mb-2">Max Risk Per Trade</p><input type="range" min={0.5} max={2} step={0.1} value={riskPct} onChange={e => setRiskPct(parseFloat(e.target.value))} className="w-full" /><p className="text-sm font-mono text-primary mt-1">{riskPct.toFixed(1)}%</p></div>
        <div><p className="text-label text-tertiary mb-2">Daily Loss Limit</p><input type="range" min={1} max={10} step={0.5} value={dailyLimit} onChange={e => setDailyLimit(parseFloat(e.target.value))} className="w-full" /><p className="text-sm font-mono text-primary mt-1">{dailyLimit.toFixed(1)}%</p></div>
        <div><p className="text-label text-tertiary mb-2">Max Open Positions</p><input type="range" min={1} max={5} step={1} value={maxPositions} onChange={e => setMaxPositions(parseInt(e.target.value))} className="w-full" /><p className="text-sm font-mono text-primary mt-1">{maxPositions}</p></div>
        <div><p className="text-label text-tertiary mb-2">Min Confidence Threshold</p><input type="range" min={50} max={90} step={1} value={confidence} onChange={e => setConfidence(parseInt(e.target.value))} className="w-full" /><p className="text-sm font-mono text-primary mt-1">{confidence}%</p></div>
        <button className="px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent/90 transition-colors">Save Changes</button>
      </div>
    </div>
  );
}
