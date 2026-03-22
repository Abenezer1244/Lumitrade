"use client";
import { useState, useEffect, useCallback } from "react";
import type { OpenPosition } from "@/types/trading";
import { useRealtime } from "./useRealtime";

export function useOpenPositions() {
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/positions")
      .then(r => r.json())
      .then(data => { setPositions(data.positions || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useRealtime({ table: "trades", event: "INSERT", filter: "status=eq.OPEN", onData: useCallback((payload: any) => {
    setPositions(prev => [...prev, payload.new as OpenPosition]);
  }, []) });

  useRealtime({ table: "trades", event: "UPDATE", onData: useCallback((payload: any) => {
    const updated = payload.new;
    if (updated.status === "CLOSED" || updated.status === "CANCELLED") {
      setPositions(prev => prev.filter(p => p.id !== updated.id));
    } else {
      setPositions(prev => prev.map(p => p.id === updated.id ? updated as OpenPosition : p));
    }
  }, []) });

  return { positions, loading };
}
