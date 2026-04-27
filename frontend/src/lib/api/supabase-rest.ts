/**
 * Centralized Supabase REST helpers for Next.js route handlers.
 *
 * The dashboard's read-only API routes all share the same boilerplate:
 *   - read NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_KEY env vars
 *   - bail with a fallback payload when either env var is missing
 *   - attach `apikey` + `Authorization: Bearer <key>` headers
 *   - call PostgREST with `cache: "no-store"`
 *   - swallow network/HTTP errors and return a fallback
 *
 * Extracting it keeps each route to its actual business logic and removes
 * the long tail of copy-paste drift between the 20+ dashboard routes.
 *
 * Trading-mutating routes (kill-switch, api-keys POST/DELETE) are NOT
 * candidates for this helper — they need explicit error responses, not
 * silent fallbacks.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY;

/** True when both Supabase env vars are configured. */
export function supabaseEnvReady(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_KEY);
}

/** Headers used for every PostgREST call against the project's Supabase. */
export function supabaseHeaders(): Record<string, string> {
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    throw new Error("supabase env not ready");
  }
  return {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
  };
}

/**
 * Fire a no-store PostgREST GET against `<SUPABASE_URL><path>` and return
 * the parsed JSON. Returns `null` if the env vars are missing or the
 * upstream responds with a non-2xx — callers decide what to substitute.
 *
 * `path` MUST begin with `/rest/v1/...`.
 */
export async function supabaseFetch<T>(
  path: string,
  init?: { extraHeaders?: Record<string, string>; signal?: AbortSignal },
): Promise<T | null> {
  if (!supabaseEnvReady()) return null;
  try {
    const res = await fetch(`${SUPABASE_URL}${path}`, {
      headers: { ...supabaseHeaders(), ...(init?.extraHeaders ?? {}) },
      cache: "no-store",
      signal: init?.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
