import { NextResponse } from "next/server";
import { supabaseFetch } from "@/lib/api/supabase-rest";

export const dynamic = "force-dynamic";

export async function GET() {
  const data = await supabaseFetch<unknown[]>(
    "/rest/v1/agent_events?select=*&order=created_at.desc&limit=50"
  );
  return NextResponse.json({ events: data ?? [] });
}
