"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import type { AccountSummary } from "@/types/system";

export function useAccount() {
  const { data, error, isLoading, mutate } = useSWR<AccountSummary>(
    "/api/account",
    fetcher,
    {
      refreshInterval: 2_000,
      revalidateOnFocus: true,
      dedupingInterval: 1_000,
    }
  );

  return {
    account: data ?? null,
    loading: isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    refetch: mutate,
  };
}
