import { test, expect, type Page } from "@playwright/test";

/**
 * End-to-end auth flow.
 *
 * These exercise the full stack — UI talks to FastAPI which talks to
 * Postgres. The HttpOnly refresh cookie + `auth_present` flag cookie +
 * in-memory access token round-trip is implicit; we assert on what the
 * user sees rather than on tokens or storage.
 *
 * Each test generates a unique email so the suite has no cross-test
 * coupling and can be re-run on a non-clean database.
 */

const PASSWORD = "correct-horse-battery-staple";

function uniqueEmail(label: string): string {
  // Random suffix keeps reruns isolated even within the same millisecond.
  const suffix = Math.random().toString(36).slice(2, 8);
  return `e2e-${label}-${Date.now()}-${suffix}@example.com`;
}

async function register(page: Page, email: string, fullName?: string): Promise<void> {
  await page.goto("/register");
  if (fullName) {
    await page.getByLabel(/full name/i).fill(fullName);
  }
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /create account/i }).click();
}

async function login(
  page: Page,
  email: string,
  password: string = PASSWORD,
): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /^sign in$/i }).click();
}

test.describe("anonymous access", () => {
  test("unauthenticated visit to /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
    // The login form is the load-bearing signal that we landed on /login —
    // its email field is the only Email input on the site.
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByRole("button", { name: /^sign in$/i })).toBeVisible();
  });
});

test.describe("registration", () => {
  test("a new user lands on the dashboard with their profile visible", async ({
    page,
  }) => {
    const email = uniqueEmail("register");
    await register(page, email, "New User");

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText("New User")).toBeVisible();
  });
});

test.describe("login", () => {
  test("existing user signs in and reaches the dashboard", async ({ page }) => {
    const email = uniqueEmail("login");
    await register(page, email);
    // Registration auto-logs us in; sign out to test the explicit login path.
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login(?:\?|$)/);

    await login(page, email);
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText(email)).toBeVisible();
  });

  test("bad password shows an inline error and stays on /login", async ({ page }) => {
    const email = uniqueEmail("badpass");
    await register(page, email);
    await page.getByRole("button", { name: /sign out/i }).click();
    // Wait for the sign-out redirect to finish before navigating to /login.
    // Without this, the next page.goto can race with logout: the
    // `auth_present` cookie is still set, middleware redirects to
    // /dashboard, and the test sees a dashboard loading state instead.
    await expect(page).toHaveURL(/\/login(?:\?|$)/);

    await login(page, email, "totally-wrong-password");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
    await expect(page.getByText(/incorrect email or password/i)).toBeVisible();
  });

  test("login is case-insensitive (regression for PR #2)", async ({ page }) => {
    // Register with mixed case, log in with UPPER case — should succeed.
    const email = uniqueEmail("CaseTest").replace("e2e-", "E2E-");
    await register(page, email);
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login(?:\?|$)/);

    await login(page, email.toUpperCase());
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

test.describe("inline validation", () => {
  test("register form blocks submit on empty fields and shows field errors", async ({
    page,
  }) => {
    // The form is client-validated via zod + react-hook-form, so a
    // submit with no input must show field errors and never reach the
    // backend. We assert on the lack of a network request to confirm.
    const apiCalls: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/v1/auth/register")) apiCalls.push(req.url());
    });

    await page.goto("/register");
    await page.getByRole("button", { name: /create account/i }).click();

    await expect(page.getByText(/email is required/i)).toBeVisible();
    await expect(
      page.getByText(/password must be at least 8 characters/i),
    ).toBeVisible();

    // Still on the register page, never POSTed to /api/v1/auth/register.
    await expect(page).toHaveURL(/\/register$/);
    expect(apiCalls).toHaveLength(0);
  });

  test("register form rejects short passwords with inline error", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Email").fill("inline-validation@example.com");
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: /create account/i }).click();

    await expect(
      page.getByText(/password must be at least 8 characters/i),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/register$/);
  });

  test("login form rejects malformed emails inline", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByLabel("Password").fill("anything");
    await page.getByRole("button", { name: /^sign in$/i }).click();

    await expect(page.getByText(/enter a valid email/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
  });
});

test.describe("logout", () => {
  test("clears the session — visiting /dashboard now redirects to /login", async ({
    page,
  }) => {
    const email = uniqueEmail("logout");
    await register(page, email);
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login(?:\?|$)/);

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
  });
});
