import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./container-tests",
  outputDir: "./test-results-container",
  workers: 1,
  use: {
    baseURL: process.env.VOLLEYCREW_CONTAINER_URL ?? "https://127.0.0.1:18443",
    ignoreHTTPSErrors: true, // Disposable localhost TLS fixture only.
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["iPhone 13"], browserName: "webkit" } },
  ],
});
