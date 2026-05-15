import { jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

/** Routes that require authentication. */
const PROTECTED_PREFIXES = ["/dashboard"];

/** Routes that authenticated users should NOT see (redirect to dashboard). */
const AUTH_PAGES = ["/login", "/register"];

/**
 * Verify the JWT's signature and expiry. SECRET_KEY is shared with the
 * backend so HS256 tokens minted by python-jose verify here too.
 */
async function isValidAccessToken(token: string | undefined): Promise<boolean> {
  if (!token) return false;
  const secret = process.env.SECRET_KEY;
  if (!secret) {
    console.error("SECRET_KEY not set — middleware cannot validate tokens");
    return false;
  }
  try {
    const { payload } = await jwtVerify(token, new TextEncoder().encode(secret));
    return payload.type === "access";
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const authed = await isValidAccessToken(request.cookies.get("auth-token")?.value);

  if (PROTECTED_PREFIXES.some((p) => pathname.startsWith(p)) && !authed) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (AUTH_PAGES.some((p) => pathname.startsWith(p)) && authed) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Run on all routes except static files and API
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
