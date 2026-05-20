/**
 * Unit tests for the typed API client.
 *
 * Scope: the bits of `api.ts` that aren't covered by Playwright —
 * `ApiError` construction and the single-flight refresh invariant in
 * `tryRefresh` (exposed via `bootstrapSession`). The full
 * `customFetch` → 401 → refresh → retry choreography is partially
 * covered by the auth E2E suite; the concurrent-refresh case is hard
 * to provoke from a browser test and lives here instead.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, bootstrapSession, getAccessToken, setAccessToken } from "./api";

describe("ApiError", () => {
  it("carries status, detail, and requestId", () => {
    const err = new ApiError(401, "bad credentials", "req-abc-123");
    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(401);
    expect(err.detail).toBe("bad credentials");
    expect(err.requestId).toBe("req-abc-123");
    expect(err.message).toBe("bad credentials"); // inherited from Error
    expect(err.name).toBe("ApiError");
  });

  it("defaults requestId to null when omitted", () => {
    const err = new ApiError(500, "boom");
    expect(err.requestId).toBeNull();
  });
});

describe("bootstrapSession / tryRefresh", () => {
  beforeEach(() => {
    // Module-level `accessToken` and `pendingRefresh` are reset between
    // tests so single-flight state from one test can't leak into another.
    setAccessToken(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns true and stashes the new access token on a 200 refresh", async () => {
    // Type the mock as `typeof fetch` so `.mock.calls` retains the
    // [input, init?] tuple shape — without it, vitest infers a 0-arg
    // signature from the implementation and indexing into calls fails.
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ access_token: "fresh-token" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootstrapSession();

    expect(ok).toBe(true);
    expect(getAccessToken()).toBe("fresh-token");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/refresh");
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("include");
  });

  it("returns false and clears the access token when refresh fails", async () => {
    // Seed a stale token; a failed refresh must clear it.
    setAccessToken("stale-token");
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootstrapSession();

    expect(ok).toBe(false);
    expect(getAccessToken()).toBeNull();
  });

  it("returns false and clears the access token when fetch throws", async () => {
    setAccessToken("stale-token");
    const fetchMock = vi.fn(async () => {
      throw new TypeError("network down");
    });
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootstrapSession();

    expect(ok).toBe(false);
    expect(getAccessToken()).toBeNull();
  });

  it("single-flights parallel refreshes — only one /refresh call under load", async () => {
    // The load-bearing invariant. Without single-flighting, two
    // concurrent 401s in the wild both call /auth/refresh; the
    // backend's rotation logic invalidates the loser's freshly-issued
    // token, the user gets logged out, and we look like clowns.
    const resolvers: ((res: Response) => void)[] = [];
    const fetchMock = vi.fn<typeof fetch>(
      () =>
        new Promise<Response>((resolve) => {
          resolvers.push(resolve);
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    // Fire ten parallel refresh attempts before any of them resolve.
    const tenRefreshes = Promise.all(
      Array.from({ length: 10 }, () => bootstrapSession()),
    );

    // Wait a microtask so all calls have queued up against the same
    // pendingRefresh promise.
    await Promise.resolve();
    await Promise.resolve();

    // Only ONE fetch hit the network — the single-flight guard worked.
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(resolvers).toHaveLength(1);

    // Resolve the single in-flight request; all ten waiters get the
    // same answer.
    resolvers[0](
      new Response(JSON.stringify({ access_token: "shared-token" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const results = await tenRefreshes;

    expect(results.every((r) => r === true)).toBe(true);
    expect(getAccessToken()).toBe("shared-token");
  });

  it("a subsequent refresh after the first completes hits the network again", async () => {
    // `pendingRefresh` clears in the finally block, so the NEXT refresh
    // after the first finishes must issue a fresh request. This is the
    // happy-path complement to the single-flight test — proving the
    // guard doesn't permanently lock out future refreshes.
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ access_token: "t" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await bootstrapSession();
    await bootstrapSession();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
