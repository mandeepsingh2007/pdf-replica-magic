/** Browser uses same-origin Next rewrite (/api/backend → FastAPI) so ngrok works.
 *  Server-side can still hit uvicorn directly.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window === "undefined"
    ? "http://127.0.0.1:8000/api"
    : "/api/backend");

const API_TIMEOUT_MS = 45_000;

export async function readJson(res: Response): Promise<any> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(
      res.ok
        ? "Server returned a non-JSON response. Restart the frontend (npm run dev)."
        : `API ${res.status}: ${text.slice(0, 120) || res.statusText}`
    );
  }
}

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
    credentials: "omit",
    ...init,
    headers,
    signal: init?.signal ?? controller.signal,
  }).finally(() => clearTimeout(timeout));
}
