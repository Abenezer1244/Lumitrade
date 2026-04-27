import { NextResponse } from "next/server";
import { supabaseEnvReady, supabaseFetch } from "@/lib/api/supabase-rest";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!supabaseEnvReady()) {
    return NextResponse.json(
      { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
      { status: 500 }
    );
  }

  const data = await supabaseFetch<unknown[]>(
    "/rest/v1/signals?select=*&order=created_at.desc&limit=50"
  );

  return NextResponse.json({ signals: data ?? [] });
}
