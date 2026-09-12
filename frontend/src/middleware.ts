import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE = "tg_auth";

const PUBLIC_PATHS = ["/gate", "/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthenticated = request.cookies.get(AUTH_COOKIE)?.value === "true";

  if (pathname.startsWith("/api/login") || pathname.startsWith("/api/backend")) {
    return NextResponse.next();
  }

  if (pathname === "/") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`)
  );

  if (pathname === "/login") {
    const url = request.nextUrl.clone();
    if (url.searchParams.has("password") || url.searchParams.has("id")) {
      url.searchParams.delete("id");
      url.searchParams.delete("password");
      if (!url.searchParams.has("error")) {
        url.searchParams.set("error", "invalid");
      }
      return NextResponse.redirect(url);
    }
    // Always show login (portal → Test Generator). Clear any old session.
    const response = NextResponse.next();
    response.cookies.delete(AUTH_COOKIE);
    return response;
  }

  if (isAuthenticated && pathname === "/gate") {
    return NextResponse.redirect(new URL("/upload", request.url));
  }

  if (!isAuthenticated && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)" ],
};
