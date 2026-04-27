import { NextResponse } from "next/server";
import { supabaseFetch } from "@/lib/api/supabase-rest";

export const dynamic = "force-dynamic";

export async function GET() {
  const trades = await supabaseFetch<unknown[]>(
    "/rest/v1/trades?select=confidence_score,outcome,pnl_usd&status=eq.CLOSED"
  );
  return NextResponse.json({ trades: trades ?? [] });
}
