/**
 * Sentry Edge runtime init.
 *
 * Loaded from `instrumentation.ts` on the Edge runtime (middleware +
 * Edge routes). No-op when `SENTRY_DSN` is unset.
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.SENTRY_ENVIRONMENT,
    tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE ?? 0),
    sendDefaultPii: false,
  });
}
