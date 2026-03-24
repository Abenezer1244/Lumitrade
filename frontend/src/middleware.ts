import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

export async function middleware(request: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // If Supabase is not configured, allow through (dev mode)
  if (!supabaseUrl || !supabaseKey) {
    return NextResponse.next();
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

  // Unauthenticated users trying to access protected routes → redirect to login
  if (!user) {
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

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
