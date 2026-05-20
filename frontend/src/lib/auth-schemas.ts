/**
 * Zod schemas for the auth forms.
 *
 * These are the **client-side** validation rules — the backend has its
 * own Pydantic validation that's the source of truth for security. The
 * client schemas exist to:
 *
 *   1. Give the user instant feedback before round-tripping to the API
 *      (no "incorrect email or password" spinner-then-error for a typo)
 *   2. Express browser-relevant constraints (password min length) that
 *      aren't expressed in the API contract anyway
 *   3. Stay type-aligned with the generated OpenAPI types — the
 *      `_AssertX` lines below fail to compile if the schema shape ever
 *      drifts from `components["schemas"]["UserLogin" | "UserCreate"]`
 */

import { z } from "zod";

import type { components } from "@/lib/api-types";

// ── Login ────────────────────────────────────────────────────────────
export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

export type LoginInput = z.infer<typeof loginSchema>;

// ── Register ─────────────────────────────────────────────────────────
export const registerSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  // 8 chars matches the backend's implicit floor and the existing HTML
  // `minLength={8}` on the field — change all three together.
  password: z.string().min(8, "Password must be at least 8 characters"),
  // Optional — submit handler coerces "" → undefined so we don't POST
  // an empty string for an unspecified name.
  full_name: z.string().max(255, "Name is too long").optional(),
});

export type RegisterInput = z.infer<typeof registerSchema>;

// ── Contract alignment ───────────────────────────────────────────────
// Compile-time guards. If the OpenAPI contract changes such that the
// generated types no longer accept what the Zod schemas produce, these
// type aliases resolve to `never` and the assignment errors at build.
// That's the load-bearing line — without it, the schemas can silently
// drift from the API.
type _AssertLogin = LoginInput extends components["schemas"]["UserLogin"]
  ? true
  : never;
type _AssertRegister = RegisterInput extends components["schemas"]["UserCreate"]
  ? true
  : never;

const _assertLogin: _AssertLogin = true;
const _assertRegister: _AssertRegister = true;

// Mark as used so the lint rule doesn't strip them.
void _assertLogin;
void _assertRegister;
