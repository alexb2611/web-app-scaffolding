/**
 * Zod schemas for the Note resource.
 *
 * Type-aligned with the generated OpenAPI types via the `_AssertX`
 * lines below — if the backend renames `body` or changes a constraint,
 * the assertion resolves to `never` and the build fails.
 */

import { z } from "zod";

import type { components } from "@/lib/api-types";

// ── Create ───────────────────────────────────────────────────────────
export const noteCreateSchema = z.object({
  title: z.string().min(1, "Title is required").max(255, "Title is too long"),
  body: z.string().min(1, "Body is required"),
});

export type NoteCreateInput = z.infer<typeof noteCreateSchema>;

// ── Contract alignment ───────────────────────────────────────────────
type _AssertCreate = NoteCreateInput extends components["schemas"]["NoteCreate"]
  ? true
  : never;

const _assertCreate: _AssertCreate = true;
void _assertCreate;
