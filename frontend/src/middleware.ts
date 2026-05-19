import { NextRequest, NextResponse } from "next/server";

/** Routes that require authentication. */
const PROTECTED_PREFIXES = ["/dashboard"];

/** Routes that authenticated users should NOT see (redirect to dashboard). */
const AUTH_PAGES = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // `auth_present` is a non-sensitive flag set alongside the HttpOnly
  // `refresh_token` cookie. It carries no credential value — it just lets
  // the middleware know whether to redirect.
  const hasToken = request.cookies.has("auth_present");

  // Redirect unauthenticated users away from protected routes
  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  if (isProtected && !hasToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect authenticated users away from auth pages
  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p));
  if (isAuthPage && hasToken) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except static files and API
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
