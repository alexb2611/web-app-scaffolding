/**
 * Typed API client.
 *
 * The access token lives in memory only (no localStorage) to keep it out
 * of reach of XSS. The refresh token is delivered via an HttpOnly cookie
 * set by the backend, so every request needs `credentials: "include"` to
 * carry it. On a 401 we attempt a silent refresh (cookie is sent
 * automatically) and retry the original request.
 */

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
  // crypto.randomUUID is available in all evergreen browsers + Node 19+.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for very old environments.
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

// ── Refresh coordination ───────────────────────────────────────────────

// If multiple requests hit a 401 at the same time, we only want one
// refresh call in flight.
let pendingRefresh: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (pendingRefresh) return pendingRefresh;
  pendingRefresh = (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
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

/** Public helper: bootstrap the in-memory token from the refresh cookie. */
export async function bootstrapSession(): Promise<boolean> {
  return tryRefresh();
}

// ── Core fetch wrapper ─────────────────────────────────────────────────

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("X-Request-ID")) {
    headers.set("X-Request-ID", newRequestId());
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const init: RequestInit = { ...options, headers, credentials: "include" };
  let res = await fetch(url, init);

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      res = await fetch(url, { ...options, headers, credentials: "include" });
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      res.status,
      body.detail ?? res.statusText,
      res.headers.get("x-request-id"),
    );
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Public API methods ─────────────────────────────────────────────────

export const api = {
  get: <T>(url: string) => request<T>(url),

  post: <T>(url: string, body?: unknown) =>
    request<T>(url, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(url: string, body?: unknown) =>
    request<T>(url, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(url: string, body?: unknown) =>
    request<T>(url, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(url: string) => request<T>(url, { method: "DELETE" }),
};
