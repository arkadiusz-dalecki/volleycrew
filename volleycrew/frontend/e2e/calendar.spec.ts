import { expect, test } from "@playwright/test";
import { adminLogin } from "./auth-helpers";

test("calendar future navigation, cancelled meeting, persistent detail and recovery", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const month = process.env.E2E_CALENDAR_MONTH!;
  await page.goto(`/calendar?month=${month}`);
  const agenda = page.locator(".agenda-list");
  await expect(agenda.getByText("Odwołane", { exact: true })).toBeVisible();
  for (const width of info.project.name !== "desktop"
    ? [360, 390, 430]
    : [1440]) {
    await page.setViewportSize({
      width,
      height: info.project.name !== "desktop" ? 844 : 1000,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`calendar-${width}.png`),
      fullPage: true,
      scale: "css",
    });
  }
  await agenda
    .getByRole("listitem")
    .filter({ hasText: "Odwołane" })
    .getByRole("button")
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/meetings/${process.env.E2E_CANCELLED_ID}$`),
  );
  await expect(
    page.getByText(
      "Spotkanie zostało odwołane. Nie powoduje oznaczeń nieobecności.",
    ),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("Odwołane", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Wróć do kalendarza" }).click();
  await expect(page).toHaveURL(new RegExp(`month=${month}$`));
  await page.getByRole("button", { name: "Następny miesiąc" }).click();
  await expect(page.locator(".agenda-list li").first()).toBeVisible();
  const targetMonth = `${Number(month.slice(0, 4)) + 10}-${month.slice(5)}`;
  await page.locator('input[type="month"]').fill(targetMonth);
  await expect(page).toHaveURL(new RegExp(`month=${targetMonth}$`));
  const open = page.getByRole("button", { name: /^Otwórz spotkanie:/ }).first();
  await expect(open).toBeEnabled();
  await open.click();
  await expect(page).toHaveURL(/\/meetings\/[a-f0-9-]+$/);
  const stableUrl = page.url();
  await expect(
    page.getByRole("heading", { name: "Spotkanie", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(stableUrl);
  await expect(
    page.getByRole("heading", { name: "Spotkanie", exact: true }),
  ).toBeVisible();
  const id = stableUrl.split("/").at(-1);
  const saved = await context.request.get(`/api/v1/meetings/${id}`);
  expect((await saved.json()).persisted).toBe(true);
  await page.screenshot({
    path: info.outputPath("meeting-detail.png"),
    fullPage: true,
    scale: "css",
  });
  await page.goto("/calendar?month=2000-01");
  await expect(
    page.getByRole("heading", { name: "Brak spotkań" }),
  ).toBeVisible();
  await page.route("**/api/v1/calendar?*", (route) => route.abort());
  await page.goto(`/calendar?month=${targetMonth}`);
  await expect(
    page.getByRole("heading", { name: "Nie udało się pobrać kalendarza" }),
  ).toBeVisible();
  await page.unroute("**/api/v1/calendar?*");
  await page.getByRole("button", { name: "Ponów", exact: true }).click();
  await expect(page.locator(".agenda-list li").first()).toBeVisible();
});
