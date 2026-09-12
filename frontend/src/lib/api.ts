/** Same-origin proxy in dev (see next.config rewrites). Set NEXT_PUBLIC_API_URL for direct/ngrok. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

const API_TIMEOUT_MS = 45_000;

/** ngrok free tier shows an interstitial — this header skips it for API calls */
export function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (
    API_BASE.includes("ngrok") ||
    (typeof window !== "undefined" && window.location.hostname.includes("ngrok"))
  ) {
    headers.set("ngrok-skip-browser-warning", "true");
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  return fetch(input, {
    credentials: "same-origin",
    ...init,
    headers,
    signal: init?.signal ?? controller.signal,
  }).finally(() => clearTimeout(timeout));
}
