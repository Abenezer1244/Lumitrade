"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import type { SystemHealth } from "@/types/system";

export function useSystemStatus() {
  const { data, error, isLoading } = useSWR<SystemHealth>(
    "/api/system/health",
    fetcher,
    {
      refreshInterval: 2_000,
      revalidateOnFocus: true,
      dedupingInterval: 1_000,
    }
  );

  return {
    health: data ?? null,
    loading: isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
  };
}
