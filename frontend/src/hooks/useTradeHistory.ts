"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import type { Trade } from "@/types/trading";

interface TradeHistoryResponse {
  trades: Trade[];
  total: number;
}

interface UseTradeHistoryParams {
  page?: number;
  limit?: number;
  pair?: string;
  outcome?: string;
}

interface UseTradeHistoryResult {
  trades: Trade[];
  total: number;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function buildTradesKey(params: UseTradeHistoryParams): string {
  const search = new URLSearchParams();
  search.set("page", String(params.page ?? 1));
  search.set("limit", String(params.limit ?? 20));
  if (params.pair) search.set("pair", params.pair);
  if (params.outcome) search.set("outcome", params.outcome);
  return `/api/trades?${search.toString()}`;
}

export function useTradeHistory(
  params: UseTradeHistoryParams = {}
): UseTradeHistoryResult {
  const key = buildTradesKey(params);

  const { data, error, isLoading, mutate } = useSWR<TradeHistoryResponse>(
    key,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 5_000,
    }
  );

  return {
    trades: data?.trades ?? [],
    total: data?.total ?? 0,
    loading: isLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    refetch: () => { mutate(); },
  };
}
