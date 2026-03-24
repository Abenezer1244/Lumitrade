"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import type { Signal } from "@/types/trading";
import { useRealtime } from "./useRealtime";

interface SignalsResponse {
  signals: Signal[];
}

const MAX_SIGNALS = 50;

export function useSignals() {
  const { data, error, isLoading, mutate } = useSWR<SignalsResponse>(
    "/api/signals?limit=50",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 5_000,
    }
  );

  const signals = data?.signals ?? [];

  useRealtime({
    table: "signals",
    event: "INSERT",
    onData: useCallback(
      (payload: Record<string, unknown>) => {
        const newSignal = (payload as { new: Signal }).new;
        mutate(
          (current) => {
            const prev = current?.signals ?? [];
            return { signals: [newSignal, ...prev].slice(0, MAX_SIGNALS) };
          },
          { revalidate: false }
        );
      },
      [mutate]
    ),
  });

  useRealtime({
    table: "signals",
    event: "UPDATE",
    onData: useCallback(
      (payload: Record<string, unknown>) => {
        const updated = (payload as { new: Signal }).new;
        mutate(
          (current) => {
            const prev = current?.signals ?? [];
            return {
              signals: prev.map((s) =>
                s.id === updated.id ? updated : s
              ),
            };
          },
          { revalidate: false }
        );
      },
      [mutate]
    ),
  });

  return {
    signals,
    loading: isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
  };
}
