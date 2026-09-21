import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE = "tg_auth";
const HINDI_COOKIE = "tg_hindi_auth";

const PUBLIC_PATHS = [
  "/",
  "/gate",
  "/login",
  "/semester",
  "/hindi",
  "/hindi/login",
  "/hindi/videos",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isEnglishAuth = request.cookies.get(AUTH_COOKIE)?.value === "true";
  const isHindiAuth = request.cookies.get(HINDI_COOKIE)?.value === "true";

  if (
    pathname.startsWith("/api/login") ||
    pathname.startsWith("/api/hindi-login") ||
    pathname.startsWith("/api/backend")
  ) {
    return NextResponse.next();
  }

  if (pathname === "/hindi/login") {
    const url = request.nextUrl.clone();
    if (url.searchParams.has("password") || url.searchParams.has("id")) {
      url.searchParams.delete("id");
      url.searchParams.delete("password");
      if (!url.searchParams.has("error")) url.searchParams.set("error", "invalid");
      return NextResponse.redirect(url);
    }
    // Visiting login clears Hindi session. Prefer set-expire over cookies.delete —
    // Next 16 was returning 404 for /hindi/login when delete() was used on next().
    const response = NextResponse.next();
    if (isHindiAuth) {
      response.cookies.set(HINDI_COOKIE, "", {
        path: "/",
        maxAge: 0,
        expires: new Date(0),
      });
    }
    return response;
  }

  if (pathname === "/login") {
    const url = request.nextUrl.clone();
    if (url.searchParams.has("password") || url.searchParams.has("id")) {
      url.searchParams.delete("id");
      url.searchParams.delete("password");
      if (!url.searchParams.has("error")) url.searchParams.set("error", "invalid");
      return NextResponse.redirect(url);
    }
    const response = NextResponse.next();
    response.cookies.delete(AUTH_COOKIE);
    return response;
  }

  if (
    pathname.startsWith("/hindi") &&
    pathname !== "/hindi" &&
    pathname !== "/hindi/videos"
  ) {
    if (!isHindiAuth) {
      const login = new URL("/hindi/login", request.url);
      if (pathname.startsWith("/hindi/ebooks")) {
        login.searchParams.set("next", pathname);
      }
      return NextResponse.redirect(login);
    }
    return NextResponse.next();
  }

  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );

  if (isAuthenticatedPath(pathname) && (isEnglishAuth || isHindiAuth)) {
    if (isEnglishAuth && pathname === "/gate") {
      return NextResponse.redirect(new URL("/upload", request.url));
    }
    return NextResponse.next();
  }

  if (!isEnglishAuth && !isPublic && !pathname.startsWith("/hindi")) {
    if (pathname.startsWith("/test") && isHindiAuth) {
      return NextResponse.next();
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

function isAuthenticatedPath(pathname: string): boolean {
  return pathname.startsWith("/test") || pathname.startsWith("/upload");
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
