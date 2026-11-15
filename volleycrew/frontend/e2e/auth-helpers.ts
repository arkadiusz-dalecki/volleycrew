import { expect, type BrowserContext } from "@playwright/test";
export async function adminLogin(context: BrowserContext) {
  const csrf = await context.request.get("/api/v1/auth/csrf");
  const response = await context.request.post("/api/v1/auth/login", {
    headers: {
      Origin: "http://127.0.0.1:5175",
      "X-CSRF-Token": (await csrf.json()).token,
    },
    data: { username: "organizer", password: "Admin-test-passphrase-123" },
  });
  expect(response.ok()).toBe(true);
}
