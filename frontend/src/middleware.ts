import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

export async function middleware(request: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // Fail closed: if Supabase is not configured, block all protected routes
  if (!supabaseUrl || !supabaseKey) {
    return new NextResponse(
      JSON.stringify({ error: "Authentication service unavailable" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  const response = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value, options } of cookiesToSet) {
          request.cookies.set(name, value);
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Public API routes (/api/v1/*) use API key auth, not session auth
  if (request.nextUrl.pathname.startsWith("/api/v1/")) {
    return response;
  }

  // Redirect unauthenticated users to login, preserving the intended destination
  if (!user) {
    const redirectUrl = new URL("/auth/login", request.url);
    redirectUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(redirectUrl);
  }

  // Authenticated dashboard pages must not be cached at the edge.
  // Without this, Railway/Fastly was serving year-old (s-maxage=31536000)
  // HTML shells back to logged-in users, so new component additions
  // (e.g. MissionControl restored 2026-04-27) never appeared even after
  // a successful redeploy. Per-user dynamic content + edge cache = stale.
  response.headers.set(
    "Cache-Control",
    "no-store, no-cache, must-revalidate, max-age=0"
  );
  response.headers.set("CDN-Cache-Control", "no-store");
  response.headers.set("Vercel-CDN-Cache-Control", "no-store");

  return response;
}

export const config = {
  matcher: [
    // Protect all dashboard pages
    "/dashboard/:path*",
    "/signals/:path*",
    "/trades/:path*",
    "/analytics/:path*",
    "/settings/:path*",
    "/journal/:path*",
    "/coach/:path*",
    "/intelligence/:path*",
    "/marketplace/:path*",
    "/copy/:path*",
    "/backtest/:path*",
    "/api-keys/:path*",
    // Protect all API routes except auth
    "/api/:path*",
  ],
};
