export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const fetcher = async <T = unknown>(url: string): Promise<T> => {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new ApiError(res.status, body.error ?? `API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
};
