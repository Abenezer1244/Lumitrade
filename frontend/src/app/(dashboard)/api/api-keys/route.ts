import { NextRequest, NextResponse } from "next/server";
import { randomBytes, createHash } from "crypto";

export const dynamic = "force-dynamic";

const ACCOUNT_ID = "7a281498-2f2e-5ecc-8583-70118edeff28";

function hashKey(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

function generateApiKey(): string {
  const bytes = randomBytes(32);
  return `sk_live_${bytes.toString("hex")}`;
}

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) return NextResponse.json({ keys: [] });

  try {
    const res = await fetch(
      `${url}/rest/v1/api_keys?select=id,label,scopes,rate_limit,active,last_used_at,created_at,key_hash&account_id=eq.${ACCOUNT_ID}&revoked_at=is.null&order=created_at.desc`,
      {
        headers: { apikey: key, Authorization: `Bearer ${key}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return NextResponse.json({ keys: [] });
    const rows = await res.json();

    // Mask key hashes — show first/last 4 of hash as identifier
    const keys = (rows as Record<string, unknown>[]).map((r) => ({
      id: r.id,
      label: r.label || "Unnamed",
      scopes: r.scopes,
      rate_limit: r.rate_limit,
      active: r.active,
      last_used_at: r.last_used_at,
      created_at: r.created_at,
      key_preview: `sk_live_${String(r.key_hash || "").slice(0, 8)}...${String(r.key_hash || "").slice(-4)}`,
    }));

    return NextResponse.json({ keys });
  } catch {
    return NextResponse.json({ keys: [] });
  }
}

export async function POST(req: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }

  let label = "Default";
  try {
    const body = (await req.json()) as { label?: string };
    if (body.label) label = body.label.slice(0, 50);
  } catch {
    // Use default label
  }

  const apiKey = generateApiKey();
  const keyHash = hashKey(apiKey);

  try {
    const res = await fetch(`${url}/rest/v1/api_keys`, {
      method: "POST",
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        Prefer: "return=representation",
      },
      body: JSON.stringify({
        account_id: ACCOUNT_ID,
        key_hash: keyHash,
        label,
        scopes: ["read_signals", "read_trades", "read_analytics"],
        rate_limit: 100,
        active: true,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err }, { status: 500 });
    }

    const rows = await res.json();
    const created = (rows as Record<string, unknown>[])[0];

    // Return the FULL key only once — user must copy it now
    return NextResponse.json({
      id: created.id,
      key: apiKey,
      label,
      created_at: created.created_at,
      message: "Copy this key now. It will not be shown again.",
    });
  } catch {
    return NextResponse.json({ error: "Failed to create key" }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }

  let keyId = "";
  try {
    const body = (await req.json()) as { id?: string };
    if (!body.id) return NextResponse.json({ error: "Missing key id" }, { status: 400 });
    keyId = body.id;
  } catch {
    return NextResponse.json({ error: "Invalid body" }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${url}/rest/v1/api_keys?id=eq.${keyId}&account_id=eq.${ACCOUNT_ID}`,
      {
        method: "PATCH",
        headers: {
          apikey: key,
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
          Prefer: "return=minimal",
        },
        body: JSON.stringify({
          revoked_at: new Date().toISOString(),
          active: false,
        }),
      }
    );

    if (!res.ok) {
      return NextResponse.json({ error: "Failed to revoke" }, { status: 500 });
    }

    return NextResponse.json({ success: true, revoked: keyId });
  } catch {
    return NextResponse.json({ error: "Failed to revoke key" }, { status: 500 });
  }
}
