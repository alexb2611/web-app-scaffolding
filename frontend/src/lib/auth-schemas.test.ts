/**
 * Unit tests for the auth-form Zod schemas.
 *
 * The interesting tests aren't "valid input parses" (that's table stakes) —
 * they're the boundary conditions: empty-but-required field, almost-an-
 * email, password just-too-short. The error PATHS are the contract with
 * the form layer (RHF reads `error.path` to know which field to surface
 * the message on), so we assert on both the success/failure boolean AND
 * the path.
 */

import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "./auth-schemas";

describe("loginSchema", () => {
  it("accepts a valid email + non-empty password", () => {
    const result = loginSchema.safeParse({
      email: "alice@example.com",
      password: "anything-non-empty",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an empty email with a path-on-email error", () => {
    const result = loginSchema.safeParse({ email: "", password: "x" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["email"]);
      expect(result.error.issues[0].message).toMatch(/required/i);
    }
  });

  it("rejects a malformed email", () => {
    const result = loginSchema.safeParse({
      email: "not-an-email",
      password: "x",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["email"]);
      expect(result.error.issues[0].message).toMatch(/valid email/i);
    }
  });

  it("rejects an empty password", () => {
    const result = loginSchema.safeParse({
      email: "alice@example.com",
      password: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["password"]);
    }
  });
});

describe("registerSchema", () => {
  it("accepts a valid registration with optional full_name omitted", () => {
    const result = registerSchema.safeParse({
      email: "bob@example.com",
      password: "longenough",
    });
    expect(result.success).toBe(true);
  });

  it("accepts full_name when provided", () => {
    const result = registerSchema.safeParse({
      email: "bob@example.com",
      password: "longenough",
      full_name: "Bob Smith",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a password shorter than 8 characters", () => {
    const result = registerSchema.safeParse({
      email: "bob@example.com",
      password: "short",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["password"]);
      expect(result.error.issues[0].message).toMatch(/at least 8/i);
    }
  });

  it("rejects a full_name longer than 255 chars", () => {
    const result = registerSchema.safeParse({
      email: "bob@example.com",
      password: "longenough",
      full_name: "x".repeat(256),
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["full_name"]);
    }
  });
});
