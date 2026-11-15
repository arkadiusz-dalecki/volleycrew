import { test, expect } from "./fixtures";

test("an old anonymous session response cannot clear a new login", async ({
  page,
}) => {
  let release = () => {};
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  let received = () => {};
  const requested = new Promise<void>((resolve) => {
    received = resolve;
  });
  let delivered = () => {};
  const delivery = new Promise<void>((resolve) => {
    delivered = resolve;
  });
  await page.route("**/api/v1/me", async (route) => {
    const response = await route.fetch();
    received();
    await delayed;
    // Successful authentication cancels this obsolete request.
    await route.fulfill({ response }).catch(() => {});
    delivered();
  });
  await page.goto("/login");
  await requested;
  await page.getByLabel("Login", { exact: true }).fill("organizer");
  await page
    .getByLabel("Hasło", { exact: true })
    .fill("Admin-test-passphrase-123");
  await page.getByRole("button", { name: "Wejdź na boisko" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  release();
  await delivery;
  await page.waitForLoadState("networkidle");
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Wyloguj" })).toBeVisible();
});

test("a late unauthorized response after logout keeps the username login usable", async ({
  page,
  context,
}) => {
  const { adminLogin } = await import("./auth-helpers");
  await adminLogin(context);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await expect(
    page.getByRole("heading", { name: "Dobrze Cię widzieć" }),
  ).toBeVisible();
  await page.evaluate(() =>
    window.dispatchEvent(new Event("volleycrew:session-expired")),
  );
  await expect(page.getByLabel("Login", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Wyloguj" })).toHaveCount(0);
});
