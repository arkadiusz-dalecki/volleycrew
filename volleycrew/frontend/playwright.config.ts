import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5175", trace: "retain-on-failure" },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "webkit",
      use: {
        ...devices["iPhone 13"],
        browserName: "webkit",
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: [
    {
      command: "python3 ../../scripts/dev.py api-server",
      url: "http://127.0.0.1:8202/api/v1/health/ready",
      reuseExistingServer: false,
      env: {
        VOLLEYCREW_DATABASE_URL:
          process.env.VOLLEYCREW_E2E_DATABASE_URL ??
          "invalid-requires-e2e-test-db",
        VOLLEYCREW_API_PORT: "8202",
        VOLLEYCREW_PUBLIC_URL: "http://127.0.0.1:5175",
        VOLLEYCREW_COOKIE_SECURE: "false",
        VOLLEYCREW_SESSION_SECRET: "isolated-playwright-test-only-key-123456",
      },
    },
    {
      command:
        "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort",
      url: "http://127.0.0.1:5175",
      reuseExistingServer: false,
      env: { VOLLEYCREW_API_PROXY: "http://127.0.0.1:8202" },
    },
  ],
});
