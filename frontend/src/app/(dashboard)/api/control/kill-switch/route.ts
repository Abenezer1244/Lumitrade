import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY;

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json(
      { error: "Server configuration error" },
      { status: 500 }
    );
  }

  try {
    // Patch the singleton system_state row with BOTH risk_state and
    // kill_switch_active. Per Codex post-fix audit: the engine's close-out
    // path (PRD:579 + audit finding #4) watches kill_switch_active. Setting
    // only risk_state leaves an "operator says halted but engine never
    // closes positions" gap. Both must move together.
    const res = await fetch(
      `${supabaseUrl}/rest/v1/system_state?id=eq.singleton`,
      {
        method: "PATCH",
        headers: {
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
          "Content-Type": "application/json",
          Prefer: "return=representation",
        },
        body: JSON.stringify({
          risk_state: "EMERGENCY_HALT",
          kill_switch_active: true,
          updated_at: new Date().toISOString(),
        }),
        cache: "no-store",
      }
    );

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { error: `Failed to activate kill switch: ${text}` },
        { status: 502 }
      );
    }

    const data = await res.json();
    return NextResponse.json({
      success: true,
      state: "EMERGENCY_HALT",
      updated_at: data?.[0]?.updated_at || new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Unknown error" },
      { status: 500 }
    );
  }
}
