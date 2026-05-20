import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for end-to-end auth flow tests.
 *
 * Tests run against the **already-running** docker-compose stack — we
 * don't use Playwright's `webServer` because the DB also needs to be
 * up, and compose is the source of truth for local + CI orchestration.
 *
 * Local: `make dev` (compose up) then `npm run test:e2e`.
 * CI: the e2e job in `.github/workflows/ci.yml` brings the stack up.
 *
 * Rate limiting MUST be disabled on the backend for E2E — the auth
 * endpoints are throttled at 5/min and the suite blows past that. Set
 * `RATE_LIMIT_ENABLED=false` in `.env` (locally) or in the CI compose
 * env block.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // CI: bail on test.only left in source. Locally that's just annoying.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // Sequential on CI keeps logs readable and avoids spurious flake on
  // shared-resource contention. Bump if the suite grows past ~30s.
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["html", { open: "never" }], ["github"]] : "list",
  timeout: 30_000,

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
