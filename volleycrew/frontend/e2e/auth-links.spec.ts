import { expect, test } from "./fixtures";

test("auth links clear the address and require reopening after reload", async ({
  page,
}) => {
  const link = `/join#${process.env.E2E_INVITE}`;
  await page.goto(link);
  await expect(page).toHaveURL(/\/join$/);
  await page.getByLabel("Imię", { exact: true }).fill("Przed odświeżeniem");
  const secret = process.env.E2E_INVITE!;
  expect(
    await page.evaluate((value) => {
      return [localStorage, sessionStorage].some((storage) =>
        Object.values(storage).some((item) => String(item).includes(value)),
      );
    }, secret),
  ).toBe(false);
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Otwórz ponownie pełny link",
  );
  await expect(
    page.getByRole("button", { name: "Dołączam do gry" }),
  ).toHaveCount(0);
  await page.goto(link);
  await expect(page.getByLabel("Imię", { exact: true })).toBeVisible();
});

test("tokens in old URL paths are discarded instead of used", async ({
  page,
}) => {
  for (const path of ["join", "reset-password"]) {
    await page.goto(`/${path}/discard-this-token`);
    await expect(page).toHaveURL(new RegExp(`/${path}$`));
    await expect(page.getByRole("alert")).toContainText(
      "Otwórz ponownie pełny link",
    );
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
  }
});
