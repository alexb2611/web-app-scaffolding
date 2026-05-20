/**
 * Sentry browser-side init.
 *
 * Loaded automatically by Next.js 15+ before any page renders. No-op
 * when `NEXT_PUBLIC_SENTRY_DSN` is unset, so a scaffold without a DSN
 * configured has zero outbound telemetry.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
    // 0.0 = errors only. Bump to 0.1–1.0 to enable performance traces.
    tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    // PII (user names, emails, IP) is off by default. The scaffold uses
    // ApiError.requestId for cross-referencing instead — see
    // `frontend/src/lib/api.ts`.
    sendDefaultPii: false,
  });
}

// Required for Next.js navigation transaction tracking when tracing is on.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
