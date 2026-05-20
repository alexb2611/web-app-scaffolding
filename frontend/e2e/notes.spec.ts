import { expect, test, type Page } from "@playwright/test";

/**
 * End-to-end tests for the Notes reference feature.
 *
 * Coverage: auth-gating, create + see in list, delete + gone from list,
 * inline validation blocks submit without a network call. Same isolation
 * pattern as `auth.spec.ts` — each test creates its own fresh user.
 */

const PASSWORD = "correct-horse-battery-staple";

function uniqueEmail(label: string): string {
  const suffix = Math.random().toString(36).slice(2, 8);
  return `e2e-${label}-${Date.now()}-${suffix}@example.com`;
}

async function registerAndOpenNotes(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(uniqueEmail("notes"));
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.getByRole("link", { name: /view notes/i }).click();
  await expect(page).toHaveURL(/\/notes$/);
}

test.describe("notes auth", () => {
  test("unauthenticated visit to /notes redirects to /login", async ({ page }) => {
    await page.goto("/notes");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
  });
});

test.describe("notes CRUD", () => {
  test("creates a note and sees it listed", async ({ page }) => {
    await registerAndOpenNotes(page);

    await page.getByLabel("Title").fill("First note");
    await page.getByLabel("Body").fill("Hello world");
    await page.getByRole("button", { name: /add note/i }).click();

    // The new note appears in the list and the form is reset.
    await expect(page.getByText("First note")).toBeVisible();
    await expect(page.getByText("Hello world")).toBeVisible();
    await expect(page.getByLabel("Title")).toHaveValue("");
    await expect(page.getByLabel("Body")).toHaveValue("");
  });

  test("creates multiple notes and orders newest first", async ({ page }) => {
    await registerAndOpenNotes(page);

    // Distinct title/body strings so each `getByText(title)` is
    // unambiguous (substring match would otherwise hit the body too).
    const notesToCreate = [
      { title: "Alpha", body: "first added" },
      { title: "Beta", body: "second added" },
      { title: "Gamma", body: "third added" },
    ];

    for (const { title, body } of notesToCreate) {
      await page.getByLabel("Title").fill(title);
      await page.getByLabel("Body").fill(body);
      await page.getByRole("button", { name: /add note/i }).click();
      await expect(page.getByText(title)).toBeVisible();
    }

    // Visual order: newest first → oldest last. The service sorts by
    // created_at DESC; this is the user-visible regression test for it.
    // Narrow to the title <p> inside each note's content wrapper —
    // `.font-medium` alone also matches shadcn Button text.
    const titles = await page
      .locator("section .min-w-0 > p.font-medium")
      .allTextContents();
    expect(titles).toEqual(["Gamma", "Beta", "Alpha"]);
  });

  test("deletes a note and it disappears from the list", async ({ page }) => {
    await registerAndOpenNotes(page);

    await page.getByLabel("Title").fill("Doomed");
    await page.getByLabel("Body").fill("about to be gone");
    await page.getByRole("button", { name: /add note/i }).click();
    await expect(page.getByText("Doomed")).toBeVisible();

    await page.getByRole("button", { name: /delete note: Doomed/i }).click();
    await expect(page.getByText("Doomed")).not.toBeVisible();
  });
});

test.describe("notes validation", () => {
  test("submit with empty fields shows inline errors and never POSTs", async ({
    page,
  }) => {
    const postCalls: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/v1/notes")) {
        postCalls.push(req.url());
      }
    });

    await registerAndOpenNotes(page);
    await page.getByRole("button", { name: /add note/i }).click();

    await expect(page.getByText(/title is required/i)).toBeVisible();
    await expect(page.getByText(/body is required/i)).toBeVisible();
    expect(postCalls).toHaveLength(0);
  });
});
