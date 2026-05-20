import path from "node:path";

import { defineConfig } from "vitest/config";

/**
 * Vitest config for fast pure-logic unit tests.
 *
 * Scope: things Playwright can't exercise cleanly — schema validation,
 * client retry choreography, pure utility functions. UI behaviour is
 * covered by Playwright at `frontend/e2e/`. Component-rendering tests
 * (React Testing Library + jsdom) are intentionally NOT set up here;
 * if a future contributor needs them they can install `@testing-library/*`
 * + `jsdom` and switch a single file's `environment` to `"jsdom"` via
 * a top-of-file `// @vitest-environment jsdom` directive.
 *
 * Path aliases are mirrored from `tsconfig.json` explicitly rather than
 * auto-imported via `vite-tsconfig-paths` — fewer deps, easier to read.
 */
export default defineConfig({
  // Vitest writes its own cache; keep it out of the Next.js build dirs.
  cacheDir: "node_modules/.cache/vite",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // Explicit globals=false — tests must `import { describe, it, expect } from "vitest"`.
    // Matches the project's TS-strict ethos: no magic globals.
    globals: false,
  },
});
