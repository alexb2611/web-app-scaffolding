/**
 * Next.js instrumentation hook — runs once at server startup.
 *
 * Sentry server + edge runtime init is wired here. Both are no-ops when
 * `NEXT_PUBLIC_SENTRY_DSN` is unset, so an unconfigured scaffold has no
 * outbound telemetry. The browser-side init lives in
 * `instrumentation-client.ts` (Next 15 convention).
 *
 * Docs: https://nextjs.org/docs/app/guides/instrumentation
 */
import * as Sentry from "@sentry/nextjs";

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

/** Capture errors thrown in React Server Components / loaders. */
export const onRequestError = Sentry.captureRequestError;
