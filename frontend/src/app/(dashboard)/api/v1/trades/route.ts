import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";

export const dynamic = "force-dynamic";

async function validateApiKey(apiKey: string, requiredScope: string): Promise<boolean> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return false;

  const keyHash = createHash("sha256").update(apiKey).digest("hex");

  try {
    const res = await fetch(
      `${url}/rest/v1/api_keys?select=id,permissions&key_hash=eq.${keyHash}&is_active=eq.true&expires_at=is.null`,
      {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return false;
    const rows = await res.json();
    if (!Array.isArray(rows) || rows.length === 0) return false;

    const scopes = (rows[0] as Record<string, unknown>).permissions as string[];
    if (!scopes.includes(requiredScope)) return false;

    // Update last_used_at
    const keyId = (rows[0] as Record<string, unknown>).id;
    await fetch(`${url}/rest/v1/api_keys?id=eq.${keyId as string}`, {
      method: "PATCH",
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({ last_used_at: new Date().toISOString() }),
    });

    return true;
  } catch {
    return false;
  }
}

function extractApiKey(req: NextRequest): string | null {
  const auth = req.headers.get("authorization");
  if (auth?.startsWith("Bearer ")) return auth.slice(7);
  return req.nextUrl.searchParams.get("api_key");
}

export async function GET(req: NextRequest) {
  const apiKey = extractApiKey(req);
  if (!apiKey) {
    return NextResponse.json(
      { error: "Missing API key. Use Authorization: Bearer sk_live_..." },
      { status: 401 }
    );
  }

  const valid = await validateApiKey(apiKey, "read_trades");
  if (!valid) {
    return NextResponse.json(
      { error: "Invalid or revoked API key, or missing read_trades scope" },
      { status: 403 }
    );
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }

  try {
    const limit = Math.min(parseInt(req.nextUrl.searchParams.get("limit") || "20"), 100);
    const status = req.nextUrl.searchParams.get("status") || "";
    let query = `${url}/rest/v1/trades?select=pair,direction,outcome,pnl_usd,pnl_pips,entry_price,exit_price,stop_loss,take_profit,confidence_score,status,exit_reason,opened_at,closed_at&order=opened_at.desc&limit=${limit}`;
    if (status === "OPEN" || status === "CLOSED") {
      query += `&status=eq.${status}`;
    }

    const res = await fetch(query, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: "no-store",
    });

    if (!res.ok) return NextResponse.json({ trades: [] });
    const trades = await res.json();

    return NextResponse.json({
      trades,
      count: Array.isArray(trades) ? trades.length : 0,
      timestamp: new Date().toISOString(),
    });
  } catch {
    return NextResponse.json({ error: "Failed to fetch trades" }, { status: 500 });
  }
}
