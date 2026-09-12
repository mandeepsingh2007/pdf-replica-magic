const LOCAL_LOGIN = "http://localhost:3000/login";

/** Production test app (second Vercel project, root `frontend/`). */
const PRODUCTION_LOGIN = "https://tests.negraphics.in/login";

function ensureLoginPath(url: string): string {
  const trimmed = url.replace(/\/$/, "");
  return trimmed.endsWith("/login") ? trimmed : `${trimmed}/login`;
}

/**
 * Login URL for the Next.js test generator.
 * On www.negraphics.in never use localhost — uses tests.negraphics.in unless env overrides.
 */
export function getTestGeneratorLoginUrl(): string {
  const fromEnv = import.meta.env.VITE_TEST_GENERATOR_URL?.trim();
  if (fromEnv) {
    return ensureLoginPath(fromEnv);
  }

  if (typeof window !== "undefined") {
    const host = window.location.hostname.toLowerCase();
    if (host === "negraphics.in" || host === "www.negraphics.in") {
      return PRODUCTION_LOGIN;
    }
  }

  if (import.meta.env.PROD) {
    return PRODUCTION_LOGIN;
  }

  return LOCAL_LOGIN;
}
