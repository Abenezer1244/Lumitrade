"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/fetcher";
import { useRealtime } from "./useRealtime";

export interface AgentEvent {
  id: string;
  agent: string;
  event_type: string;
  pair: string;
  severity: string;
  title: string;
  detail: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface EventsResponse {
  events: AgentEvent[];
}

export function useAgentEvents(limit = 50) {
  const { data, isLoading, mutate } = useSWR<EventsResponse>(
    "/api/events",
    fetcher,
    {
      refreshInterval: 5_000,
      revalidateOnFocus: false,
      dedupingInterval: 3_000,
    }
  );

  const events = data?.events ?? [];

  // Real-time subscription for new events
  useRealtime({
    table: "agent_events",
    event: "INSERT",
    onData: useCallback(
      (payload: Record<string, unknown>) => {
        const newEvent = (payload as { new: AgentEvent }).new;
        mutate(
          (current) => ({
            events: [newEvent, ...(current?.events ?? [])].slice(0, limit),
          }),
          { revalidate: false }
        );
      },
      [mutate, limit]
    ),
  });

  return { events, loading: isLoading };
}
