/**
 * Backend API authentication helper.
 * Adds the INTERNAL_API_SECRET Bearer token to requests
 * that hit authenticated endpoints on the trading engine.
 */

const INTERNAL_API_SECRET = process.env.INTERNAL_API_SECRET || "";

/** Headers for authenticated backend requests. */
export function backendAuthHeaders(
  extra?: Record<string, string>
): Record<string, string> {
  return {
    ...(INTERNAL_API_SECRET
      ? { Authorization: `Bearer ${INTERNAL_API_SECRET}` }
      : {}),
    ...extra,
  };
}
