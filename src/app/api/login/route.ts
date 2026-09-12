import { NextResponse } from "next/server";

import { requestIsSecure } from "@/lib/auth-cookie";

const AUTH_COOKIE = "tg_auth";
const VALID_ID = "testid";
const VALID_PASSWORD = "NeGraphics@2026";

async function readCredentials(request: Request): Promise<{ id: string; password: string }> {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const body = (await request.json()) as { id?: string; password?: string };
    return {
      id: body.id?.trim() ?? "",
      password: (body.password ?? "").trim(),
    };
  }

  const form = await request.formData();
  return {
    id: String(form.get("id") ?? "").trim(),
    password: String(form.get("password") ?? "").trim(),
  };
}

function wantsJsonResponse(request: Request): boolean {
  const accept = request.headers.get("accept") ?? "";
  const contentType = request.headers.get("content-type") ?? "";
  return accept.includes("application/json") || contentType.includes("application/json");
}

function redirectBase(request: Request): string {
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  const proto =
    request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ??
    (requestIsSecure(request) ? "https" : "http");
  if (host) {
    return `${proto}://${host}`;
  }
  return new URL(request.url).origin;
}

function applyAuthCookie(response: NextResponse, request: Request): void {
  const secure = requestIsSecure(request) || process.env.NODE_ENV === "production";
  response.cookies.set(AUTH_COOKIE, "true", {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export async function POST(request: Request) {
  let id: string;
  let password: string;

  try {
    ({ id, password } = await readCredentials(request));
  } catch {
    if (wantsJsonResponse(request)) {
      return NextResponse.json({ error: "Invalid request" }, { status: 400 });
    }
    return NextResponse.redirect(new URL("/login?error=bad_request", redirectBase(request)), 303);
  }

  const ok = id === VALID_ID && password === VALID_PASSWORD;
  const base = redirectBase(request);

  if (!ok) {
    if (wantsJsonResponse(request)) {
      return NextResponse.json(
        { error: "Invalid ID or password. Please try again." },
        { status: 401 }
      );
    }
    return NextResponse.redirect(new URL("/login?error=invalid", base), 303);
  }

  if (wantsJsonResponse(request)) {
    const response = NextResponse.json({ success: true });
    applyAuthCookie(response, request);
    return response;
  }

  const response = NextResponse.redirect(new URL("/upload", base), 303);
  applyAuthCookie(response, request);
  return response;
}

export async function GET(request: Request) {
  return NextResponse.redirect(new URL("/login", redirectBase(request)), 307);
}
