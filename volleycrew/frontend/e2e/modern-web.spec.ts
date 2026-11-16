import { expect, test } from "@playwright/test";
import { adminLogin } from "./auth-helpers";
import { audit } from "./ui-helpers";

test("password confirmation identifies the invalid field and reveal keeps its value", async ({
  page,
  context,
}) => {
  await adminLogin(context);
  await page.goto("/profile");
  const password = page.getByLabel("Nowe hasło", { exact: true });
  const repeat = page.getByLabel("Powtórz nowe hasło", { exact: true });
  await page
    .getByLabel("Obecne hasło", { exact: true })
    .fill("Admin-test-passphrase-123");
  await password.fill("  Nowe-hasło-123  ");
  await repeat.fill("Inne-hasło-123");
  let writes = 0;
  await page.route("**/api/v1/me/password", (route) => {
    writes++;
    return route.abort();
  });
  await page.getByRole("button", { name: "Zmień hasło", exact: true }).click();
  await expect(repeat).toBeFocused();
  await expect(repeat).toHaveAttribute("aria-invalid", "true");
  await expect(repeat).toHaveAccessibleDescription(
    /Podane hasła muszą być takie same/,
  );
  expect(writes).toBe(0);
  await repeat.fill("  Nowe-hasło-123  ");
  await expect(repeat).not.toHaveAttribute("aria-invalid", "true");
  expect(
    await repeat.evaluate((e: HTMLInputElement) => e.checkValidity()),
  ).toBe(true);
  const reveal = page.getByRole("button", {
    name: "Pokaż hasło: Nowe hasło",
    exact: true,
  });
  await reveal.click();
  await expect(reveal).toHaveAttribute("aria-pressed", "true");
  await expect(password).toHaveAttribute("type", "text");
  await expect(password).toHaveValue("  Nowe-hasło-123  ");
  await reveal.click();
  await expect(password).toHaveAttribute("type", "password");
  await expect(password).toHaveAttribute("autocomplete", "new-password");
  expect(await audit(page)).toEqual([]);
});

test("signup and reset reject mismatched passwords before sending", async ({
  page,
}) => {
  for (const route of [
    `/join#${process.env.E2E_INVITE}`,
    "/reset-password#review-invalid-grant",
  ]) {
    await page.goto(route);
    if (route.startsWith("/join")) {
      await page.getByLabel("Imię", { exact: true }).fill("Test");
      await page.getByLabel("Nazwisko", { exact: true }).fill("Formularza");
    }
    await page.getByLabel("Login", { exact: true }).fill("review-user");
    await page
      .getByLabel(route.startsWith("/join") ? "Twoje hasło" : "Nowe hasło", {
        exact: true,
      })
      .fill("Hasło-testowe-123");
    const repeat = page.getByLabel(
      route.startsWith("/join") ? "Powtórz hasło" : "Powtórz nowe hasło",
      { exact: true },
    );
    await repeat.fill("Inne-hasło-123");
    await page
      .getByRole("button", {
        name: route.startsWith("/join")
          ? "Dołączam do gry"
          : "Ustaw nowe hasło",
      })
      .click();
    await expect(repeat).toBeFocused();
    await expect(repeat).toHaveAttribute("aria-invalid", "true");
  }
});

test("browser text preferences scale headings and preserve narrow layouts", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of [
    "/",
    "/calendar",
    "/ranking",
    "/profile",
    "/admin/settings",
  ]) {
    await page.goto(route);
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible();
    const original = await heading.evaluate((e) =>
      parseFloat(getComputedStyle(e).fontSize),
    );
    await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
    expect(
      await heading.evaluate((e) => parseFloat(getComputedStyle(e).fontSize)),
    ).toBeCloseTo(original * 2, 0);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    // An enlarged administrator list can exceed WebKit's maximum bitmap size.
    // Keep the complete layout assertions above, and capture bounded viewports.
    for (const position of ["top", "bottom"]) {
      await page.evaluate(
        (edge) =>
          window.scrollTo(
            0,
            edge === "top" ? 0 : document.documentElement.scrollHeight,
          ),
        position,
      );
      await page.screenshot({
        path: info.outputPath(
          `${route.replaceAll("/", "_") || "meeting"}-text-200-${position}.png`,
        ),
        fullPage: false,
        scale: "css",
      });
    }
  }
});

test("modal scroll containment preserves the background position", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  await page.goto("/admin/settings");
  await page
    .getByRole("button", { name: "Zablokuj", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  expect(
    await dialog.evaluate((e) => getComputedStyle(e).overscrollBehaviorY),
  ).toBe("contain");
  expect(
    await dialog.evaluate((e) => getComputedStyle(e, "::backdrop").overflow),
  ).toBe("hidden");
  // Mobile WebKit cannot generate wheel input, and Safari does not yet contain
  // scroll on non-overflowing containers. Native focus containment still applies.
  if (info.project.name !== "webkit") {
    const before = await page.evaluate(() => scrollY);
    await page.mouse.move(3, 3);
    await page.mouse.wheel(0, 600);
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => scrollY)).toBe(before);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("loading data keeps the footer outside the initial viewport", async ({
  page,
  context,
}) => {
  await adminLogin(context);
  for (const [path, endpoint, ready] of [
    ["/", "**/api/v1/meetings/next", ".meeting-card"],
    ["/ranking", "**/api/v1/ranking?*", ".ranking-list"],
  ]) {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route(endpoint, async (route) => {
      await pending;
      await route.continue();
    });
    await page.goto(path);
    await expect(page.locator(".loading-card").first()).toBeVisible();
    // Wait for the private shell as well as the route chunk to load.
    await expect(page.locator(".app-footer")).toBeAttached();
    expect(
      await page
        .locator(".app-footer")
        .evaluate((e) => e.getBoundingClientRect().top >= innerHeight),
    ).toBe(true);
    release();
    await expect(page.locator(ready)).toBeVisible();
    expect(
      await page
        .locator(".app-footer")
        .evaluate((e) => e.getBoundingClientRect().top >= innerHeight),
    ).toBe(true);
    await page.unroute(endpoint);
  }
});

test("a failed route download offers recovery and leaves navigation available", async ({
  page,
  context,
}) => {
  await adminLogin(context);
  await page.route("**/src/features/auth/AdminSettings.tsx*", (route) =>
    route.abort(),
  );
  await page.goto("/admin/settings");
  await expect(
    page.getByRole("heading", { name: "Nie udało się otworzyć widoku" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Wczytaj ponownie" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Ranking", exact: true })
    .filter({ visible: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ranking ekipy" }),
  ).toBeVisible();
});
