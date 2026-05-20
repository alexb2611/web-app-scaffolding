/**
 * Unit tests for `noteCreateSchema`.
 *
 * Asserts on both success and the error `path` — the path is the
 * contract RHF reads to surface the message on the right field, so
 * a regression that points at the wrong path would silently break
 * the inline-error UX.
 */

import { describe, expect, it } from "vitest";

import { noteCreateSchema } from "./note-schemas";

describe("noteCreateSchema", () => {
  it("accepts a valid title + body", () => {
    const result = noteCreateSchema.safeParse({
      title: "Reminder",
      body: "Buy milk",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an empty title with a path-on-title error", () => {
    const result = noteCreateSchema.safeParse({ title: "", body: "ok" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["title"]);
      expect(result.error.issues[0].message).toMatch(/required/i);
    }
  });

  it("rejects an empty body with a path-on-body error", () => {
    const result = noteCreateSchema.safeParse({ title: "ok", body: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["body"]);
      expect(result.error.issues[0].message).toMatch(/required/i);
    }
  });

  it("rejects a title longer than 255 characters", () => {
    const result = noteCreateSchema.safeParse({
      title: "x".repeat(256),
      body: "ok",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["title"]);
    }
  });
});
