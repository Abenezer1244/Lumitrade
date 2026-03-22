"use client";
import { useState, useEffect, useCallback } from "react";
import type { Signal } from "@/types/trading";
import { useRealtime } from "./useRealtime";

const MAX_SIGNALS = 50;

export function useSignals() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/signals?limit=50")
      .then(r => r.json())
      .then(data => { setSignals(data.signals || []); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  useRealtime({ table: "signals", event: "INSERT", onData: useCallback((payload: any) => {
    setSignals(prev => [payload.new as Signal, ...prev].slice(0, MAX_SIGNALS));
  }, []) });

  useRealtime({ table: "signals", event: "UPDATE", onData: useCallback((payload: any) => {
    setSignals(prev => prev.map(s => s.id === payload.new.id ? payload.new as Signal : s));
  }, []) });

  return { signals, loading, error };
}
