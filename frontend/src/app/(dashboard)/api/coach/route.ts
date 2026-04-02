import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

interface TradeRow {
  pair: string;
  direction: string;
  status: string;
  pnl_usd: number | null;
  pnl_pips: number | null;
  confidence_score: number | null;
  exit_reason: string | null;
  opened_at: string;
  closed_at: string | null;
}

interface ClaudeMessage {
  role: "user" | "assistant";
  content: string;
}

interface ClaudeResponse {
  content: Array<{ type: string; text: string }>;
  error?: { message: string };
}

function formatTradeHistory(trades: TradeRow[]): string {
  if (trades.length === 0) return "No closed trades yet.";

  return trades
    .map((t, i) => {
      const pnl = t.pnl_usd !== null ? `$${t.pnl_usd.toFixed(2)}` : "N/A";
      const pips = t.pnl_pips !== null ? `${t.pnl_pips.toFixed(1)} pips` : "N/A";
      const conf = t.confidence_score !== null ? `${(t.confidence_score * 100).toFixed(0)}%` : "N/A";
      const outcome = t.pnl_usd !== null ? (t.pnl_usd >= 0 ? "WIN" : "LOSS") : "UNKNOWN";
      return `#${i + 1} | ${t.pair} ${t.direction} | ${outcome} | P&L: ${pnl} (${pips}) | Confidence: ${conf} | Exit: ${t.exit_reason ?? "N/A"} | ${t.closed_at ?? t.opened_at}`;
    })
    .join("\n");
}

export async function POST(req: NextRequest) {
  const anthropicKey = process.env.ANTHROPIC_API_KEY;
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_SERVICE_KEY;

  if (!anthropicKey) {
    return NextResponse.json(
      { error: "Server misconfigured: missing ANTHROPIC_API_KEY" },
      { status: 500 }
    );
  }

  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.json(
      { error: "Server misconfigured: missing Supabase credentials" },
      { status: 500 }
    );
  }

  let message: string;
  try {
    const body = (await req.json()) as { message?: string };
    if (!body.message || typeof body.message !== "string" || body.message.trim().length === 0) {
      return NextResponse.json({ error: "Message is required" }, { status: 400 });
    }
    message = body.message.trim();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  // Fetch recent closed trades from Supabase
  let tradeHistory = "No trade data available.";
  try {
    const tradesRes = await fetch(
      `${supabaseUrl}/rest/v1/trades?select=pair,direction,status,pnl_usd,pnl_pips,confidence_score,exit_reason,opened_at,closed_at&status=eq.CLOSED&order=closed_at.desc&limit=20`,
      {
        headers: {
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
        },
        cache: "no-store",
      }
    );

    if (tradesRes.ok) {
      const trades = (await tradesRes.json()) as TradeRow[];
      tradeHistory = formatTradeHistory(trades);
    }
  } catch {
    // If trade fetch fails, proceed with empty history — the coach can still answer general questions
  }

  const systemPrompt = `You are Lumitrade's AI trading coach. You have access to the user's complete trade history below. Answer questions about trades, explain outcomes, and provide specific recommendations. Be concise and data-driven. Reference specific trades when relevant.\n\nTRADE HISTORY:\n${tradeHistory}`;

  // Call Claude API via raw fetch
  try {
    const claudeRes = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": anthropicKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 1024,
        system: systemPrompt,
        messages: [{ role: "user", content: message }] as ClaudeMessage[],
      }),
    });

    if (!claudeRes.ok) {
      const errBody = (await claudeRes.json().catch(() => null)) as ClaudeResponse | null;
      const errMsg = errBody?.error?.message ?? `Claude API returned ${claudeRes.status}`;
      return NextResponse.json({ error: errMsg }, { status: 502 });
    }

    const data = (await claudeRes.json()) as ClaudeResponse;
    const textBlock = data.content.find((b) => b.type === "text");
    const response = textBlock?.text ?? "No response generated.";

    return NextResponse.json({ response });
  } catch {
    return NextResponse.json(
      { error: "Failed to reach Claude API" },
      { status: 502 }
    );
  }
}
