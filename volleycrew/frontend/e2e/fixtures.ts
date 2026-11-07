import { execFileSync } from "node:child_process";
import { test as base } from "@playwright/test";
export { expect } from "@playwright/test";

// Registration tests share the proxy's IP; their protection windows must not
// bleed between independent browser projects. Production limits are unchanged.
export const test = base.extend<{ isolatedAuthLimits: void }>({
  isolatedAuthLimits: [
    // Playwright requires a destructured dependency argument, even with no dependencies.
    // eslint-disable-next-line no-empty-pattern
    async ({}, use) => {
      const url = process.env.VOLLEYCREW_E2E_DATABASE_URL;
      if (!url || !new URL(url).pathname.endsWith("_test"))
        throw new Error("Auth fixtures require a disposable *_test database");
      execFileSync("python3", ["../../scripts/dev.py", "e2e-reset-limits"], {
        env: { ...process.env, VOLLEYCREW_DATABASE_URL: url },
        stdio: "pipe",
      });
      await use();
    },
    { auto: true },
  ],
});
