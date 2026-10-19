import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Flags the ordinary "declare loading, then fetch, then setState in
      // the promise callback" pattern used by every data-fetching hook in
      // this app (no SWR/react-query -- CLAUDE.md allows no new
      // dependencies beyond openapi-typescript and Playwright). The
      // pattern is correct and necessary without a fetch library;
      // downgraded to a warning rather than silenced outright, so a
      // genuinely careless setState-in-effect still shows up.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
