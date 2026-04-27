/**
 * Backend API authentication helper.
 * Adds the INTERNAL_API_SECRET Bearer token to requests
 * that hit authenticated endpoints on the trading engine.
 *
 * Secret is read per-call from process.env so that Railway env-var
 * updates are picked up without restarting the process.
 */

/** Headers for authenticated backend requests. */
export function backendAuthHeaders(
  extra?: Record<string, string>
): Record<string, string> {
  const secret = process.env.INTERNAL_API_SECRET || "";
  return {
    ...(secret ? { Authorization: `Bearer ${secret}` } : {}),
    ...extra,
  };
}
