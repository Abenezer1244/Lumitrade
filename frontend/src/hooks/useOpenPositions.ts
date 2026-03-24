"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import type { OpenPosition } from "@/types/trading";
import { useRealtime } from "./useRealtime";

interface PositionsResponse {
  positions: OpenPosition[];
}

export function useOpenPositions() {
  const { data, error, isLoading, mutate } = useSWR<PositionsResponse>(
    "/api/positions",
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 5_000,
    }
  );

  const positions = data?.positions ?? [];

  useRealtime({
    table: "trades",
    event: "INSERT",
    filter: "status=eq.OPEN",
    onData: useCallback(
      (payload: Record<string, unknown>) => {
        const newPos = (payload as { new: OpenPosition }).new;
        mutate(
          (current) => ({
            positions: [...(current?.positions ?? []), newPos],
          }),
          { revalidate: false }
        );
      },
      [mutate]
    ),
  });

  useRealtime({
    table: "trades",
    event: "UPDATE",
    onData: useCallback(
      (payload: Record<string, unknown>) => {
        const updated = (payload as { new: OpenPosition & { status: string } }).new;
        mutate(
          (current) => {
            const prev = current?.positions ?? [];
            if (updated.status === "CLOSED" || updated.status === "CANCELLED") {
              return { positions: prev.filter((p) => p.id !== updated.id) };
            }
            return {
              positions: prev.map((p) =>
                p.id === updated.id ? (updated as OpenPosition) : p
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
    positions,
    loading: isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
  };
}
