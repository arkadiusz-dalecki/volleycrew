import { expect, test } from "@playwright/test";
import { audit, touchTargets } from "./ui-helpers";
import { adminLogin } from "./auth-helpers";

test("UI routes, contrast and touch targets across viewport widths", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const routes = [
    ["/", ".meeting-card"],
    [`/calendar?month=${process.env.E2E_CALENDAR_MONTH}`, ".agenda-list"],
    ["/ranking", ".ranking-list"],
    ["/profile", ".private-status"],
    ["/admin/settings", ".admin-player-list"],
    [`/meetings/${process.env.E2E_CANCELLED_ID}`, ".meeting-cancelled"],
  ];
  const violations = [];
  for (const [route, selector] of routes) {
    await page.goto(route);
    await expect(page.locator(selector).first()).toBeVisible();
    violations.push({ route, issues: await audit(page) });
    for (const width of info.project.name === "desktop"
      ? [768, 1440]
      : [360, 390, 430]) {
      await page.setViewportSize({
        width,
        height: info.project.name === "desktop" ? 1000 : 844,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(await touchTargets(page)).toEqual([]);
      await page.screenshot({
        path: info.outputPath(
          `${route.split("?")[0].replaceAll("/", "_") || "meeting"}-${width}.png`,
        ),
        fullPage: true,
      });
    }
  }
  expect(violations.filter((v) => v.issues.length)).toEqual([]);
});

test("network failure keeps forms; expired session clears private view and returns to requested route", async ({
  page,
  context,
}) => {
  await page.clock.install();
  await adminLogin(context);
  await page.goto("/profile");
  const nickname = page.getByLabel("Przydomek (opcjonalnie)");
  const original = await nickname.inputValue();
  await nickname.fill("Niezapisany szkic");
  await context.setOffline(true);
  await expect(
    page.getByText("Brak połączenia.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zapisz dane", exact: true }).click();
  await expect(
    page.getByText("Nie udało się połączyć z usługą.", { exact: false }),
  ).toBeVisible();
  await expect(nickname).toHaveValue("Niezapisany szkic");
  await context.setOffline(false);
  const saved = await context.request.get("/api/v1/me");
  expect((await saved.json()).nickname ?? "").toBe(original);
  await page.route("**/api/v1/me", (route) => route.abort());
  await page.clock.fastForward(31_000);
  // Failed reads retry once; failed writes never retry automatically.
  await page.clock.fastForward(2_000);
  await expect(
    page.getByRole("button", { name: "Sprawdź połączenie" }),
  ).toBeVisible();
  await expect(nickname).toHaveValue("Niezapisany szkic");
  await page.unroute("**/api/v1/me");
  await context.clearCookies();
  await page.getByRole("button", { name: "Sprawdź połączenie" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", {
      name: "Prywatna historia obecności",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.locator(`input[value="${process.env.E2E_ADMIN_ID}"]`).check();
  await page.getByLabel("PIN", { exact: true }).fill("123456");
  await page.getByRole("button", { name: "Wejdź na boisko" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(nickname).toHaveValue(original);
});

test("confirmation dialog traps keyboard focus, Escape cancels and restores trigger", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  await page.goto("/admin/settings");
  const trigger = page
    .getByRole("button", { name: "Zablokuj", exact: true })
    .first();
  await trigger.click();
  const dialog = page.getByRole("dialog", {
    name: "Zablokować profil?",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Anuluj", exact: true }),
  ).toBeFocused();
  await page.keyboard.press(info.project.name === "webkit" ? "Alt+Tab" : "Tab");
  await expect(
    dialog.getByRole("button", { name: "Potwierdź", exact: true }),
  ).toBeFocused();
  await page.keyboard.press(
    info.project.name === "webkit" ? "Alt+Shift+Tab" : "Shift+Tab",
  );
  await expect(
    dialog.getByRole("button", { name: "Anuluj", exact: true }),
  ).toBeFocused();
  await page
    .locator(".brand:visible")
    .first()
    .evaluate((element: HTMLElement) => element.focus());
  expect(
    await dialog.evaluate((element) =>
      element.contains(document.activeElement),
    ),
  ).toBe(true);
  expect(await audit(page)).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("public access screens and local install assets", async ({ page }) => {
  for (const [route, label] of [
    ["/login", "Dobrze Cię widzieć"],
    [`/join#${process.env.E2E_INVITE}`, "Dołącz do ekipy"],
    ["/reset-pin#invalid-test-token", "Nowy PIN, ta sama ekipa"],
  ]) {
    await page.goto(route);
    await expect(
      page.getByRole("heading", { name: label, exact: true }),
    ).toBeVisible();
    await expect(page.locator("form")).toBeVisible();
    expect(await audit(page)).toEqual([]);
    expect(await touchTargets(page)).toEqual([]);
  }
  const manifest = await (
    await page.request.get("/manifest.webmanifest")
  ).json();
  expect(manifest.start_url).toBe("./");
  expect(manifest.display).toBe("standalone");
  expect((await page.request.get("/icons/volleycrew.svg")).ok()).toBe(true);
  expect(
    await page.evaluate(async () => ({
      workers: (await navigator.serviceWorker.getRegistrations()).length,
      caches: await caches.keys(),
      external: performance
        .getEntriesByType("resource")
        .map((entry) => entry.name)
        .filter(
          (url) =>
            !url.startsWith(location.origin) &&
            !url.startsWith("data:") &&
            !url.startsWith("blob:"),
        ),
    })),
  ).toEqual({ workers: 0, caches: [], external: [] });
});

test("mobile keyboard viewport hides the bottom nav; short dialogs remain scrollable", async ({
  page,
  context,
}, info) => {
  test.skip(info.project.name === "desktop", "Mobile viewport behavior");
  await adminLogin(context);
  await page.goto("/profile");
  await page.getByLabel("Przydomek (opcjonalnie)").focus();
  // Geometry simulation only: actual OS keyboard/safe area needs a physical-device check.
  await page.evaluate(() => {
    Object.defineProperty(visualViewport!, "height", {
      configurable: true,
      get: () => innerHeight - 320,
    });
    visualViewport!.dispatchEvent(new Event("resize"));
  });
  await expect(page.locator("html")).toHaveAttribute(
    "data-keyboard-open",
    "true",
  );
  await expect(
    page.getByRole("navigation", { name: "Nawigacja mobilna", exact: true }),
  ).toBeHidden();
  await page.evaluate(() => {
    Reflect.deleteProperty(visualViewport!, "height");
    (document.activeElement as HTMLElement).blur();
    visualViewport!.dispatchEvent(new Event("resize"));
  });
  await expect(
    page.getByRole("navigation", { name: "Nawigacja mobilna", exact: true }),
  ).toBeVisible();
  await page.goto("/admin/settings");
  await page.setViewportSize({ width: 360, height: 350 });
  await page
    .getByRole("button", { name: "Zablokuj", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect
    .poll(() =>
      dialog.evaluate((el) => {
        const rect = el.getBoundingClientRect();
        return (
          rect.top >= 0 &&
          rect.bottom <= innerHeight &&
          getComputedStyle(el).overflowY === "auto"
        );
      }),
    )
    .toBe(true);
  const cancel = dialog.getByRole("button", { name: "Anuluj", exact: true });
  await cancel.scrollIntoViewIfNeeded();
  await cancel.click();
  await expect(dialog).toHaveCount(0);
});
