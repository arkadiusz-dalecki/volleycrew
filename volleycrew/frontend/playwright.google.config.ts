import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testDir: "./google-tests",
  webServer: (Array.isArray(base.webServer) ? base.webServer : []).map(
    (server, index) =>
      index === 0
        ? {
            ...server,
            command: "python3 ../../scripts/dev.py google-e2e-server",
            env: {
              ...server.env,
              VOLLEYCREW_GOOGLE_CLIENT_ID:
                "browser-test.apps.googleusercontent.com",
              VOLLEYCREW_GOOGLE_CLIENT_SECRET: "browser-test-secret",
            },
          }
        : server,
  ),
});
