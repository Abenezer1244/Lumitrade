"use client";
import { useEffect, useRef } from "react";
import { createClient } from "@/lib/supabase";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface UseRealtimeOptions {
  table: string;
  event?: "INSERT" | "UPDATE" | "DELETE" | "*";
  filter?: string;
  onData: (payload: any) => void;
}

export function useRealtime({ table, event = "*", filter, onData }: UseRealtimeOptions) {
  const onDataRef = useRef(onData);
  onDataRef.current = onData;

  useEffect(() => {
    const supabase = createClient();
    if (!supabase) return;

    const channel = supabase
      .channel(`realtime:${table}`)
      .on("postgres_changes", { event, schema: "public", table, filter }, (payload: any) => onDataRef.current(payload))
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [table, event, filter]);
}
