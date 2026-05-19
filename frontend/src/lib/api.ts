/**
 * Typed API client.
 *
 * Powered by `openapi-fetch` against types generated from the backend's
 * OpenAPI schema (`api-types.ts`). Path strings, query params, request
 * bodies, and response shapes are all inferred — change the backend
 * contract and call sites here fail to compile until they're updated.
 *
 * The access token lives in memory only (no localStorage) to keep it
 * out of reach of XSS. The refresh token is delivered via an HttpOnly
 * cookie set by the backend, so we pass `credentials: "include"` and
 * the cookie rides along automatically.
 *
 * Auth + X-Request-ID + 401-refresh-retry all live in a `customFetch`
 * passed to `createClient`. Doing it here (rather than via middleware)
 * keeps the retry logic in control of the request lifecycle — we own
 * the original Request and can clone it before retrying.
 */

import createClient from "openapi-fetch";

import type { paths } from "./api-types";

// ── In-memory access token ─────────────────────────────────────────────

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

// ── API error ──────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public requestId: string | null = null,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

// ── Request ID ────────────────────────────────────────────────────────

function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

// ── Refresh coordination ───────────────────────────────────────────────

let pendingRefresh: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (pendingRefresh) return pendingRefresh;
  pendingRefresh = (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "X-Request-ID": newRequestId() },
      });
      if (!res.ok) {
        setAccessToken(null);
        return false;
      }
      const data = (await res.json()) as { access_token: string };
      setAccessToken(data.access_token);
      return true;
    } catch {
      setAccessToken(null);
      return false;
    } finally {
      pendingRefresh = null;
    }
  })();
  return pendingRefresh;
}

/** Bootstrap the in-memory access token from the HttpOnly refresh cookie. */
export async function bootstrapSession(): Promise<boolean> {
  return tryRefresh();
}

// ── customFetch: auth + X-Request-ID + 401 retry ───────────────────────

async function customFetch(req: Request): Promise<Response> {
  if (!req.headers.has("X-Request-ID")) {
    req.headers.set("X-Request-ID", newRequestId());
  }
  if (accessToken) {
    req.headers.set("Authorization", `Bearer ${accessToken}`);
  }

  // Clone before the first send so we can replay on 401. Bodies are
  // single-consumption streams; the clone is the only safe replay path.
  const retryReq = req.clone();
  const firstResponse = await fetch(req);

  if (firstResponse.status !== 401) return firstResponse;

  const refreshed = await tryRefresh();
  if (!refreshed) return firstResponse;

  if (accessToken) {
    retryReq.headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return fetch(retryReq);
}

// ── Typed client ──────────────────────────────────────────────────────

export const client = createClient<paths>({
  credentials: "include",
  fetch: customFetch,
});

/**
 * Throw on `{ error }` responses so call sites can stay terse.
 * Returns `data` directly on success.
 */
export async function unwrap<T>(
  promise: Promise<{
    data?: T;
    error?: unknown;
    response: Response;
  }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (error !== undefined || !response.ok) {
    const detail =
      typeof error === "object" && error !== null && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, detail, response.headers.get("x-request-id"));
  }
  return data as T;
}
