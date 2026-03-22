"use client";
import { useState, useEffect } from "react";
import type { SystemHealth } from "@/types/system";

const POLL_INTERVAL = 30_000;

export function useSystemStatus() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch("/api/system/health");
        if (res.ok) setHealth(await res.json());
      } catch { /* keep last known state */ }
      finally { setLoading(false); }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return { health, loading };
}
