import { adminLogin } from "./auth-helpers";
import { expect, test } from "@playwright/test";

test("shell calls the real API and navigation survives reload", async ({
  page,
  context,
}, testInfo) => {
  await adminLogin(context);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await expect(page.getByText("Połączenie z usługą działa")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("meeting.png"),
    fullPage: true,
    scale: "css",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const nav = page.getByRole("navigation", {
    name:
      testInfo.project.name !== "desktop" ? "Nawigacja mobilna" : "Menu główne",
    exact: true,
  });
  for (const [label, heading, path] of [
    ["Kalendarz", "Kalendarz", "/calendar"],
    ["Ranking", "Ranking ekipy", "/ranking"],
    ["Mój profil", "Mój profil", "/profile"],
  ]) {
    await nav.getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await page.reload();
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
