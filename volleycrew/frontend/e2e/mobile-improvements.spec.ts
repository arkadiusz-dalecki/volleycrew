import { expect, test } from "./fixtures";
import { adminLogin } from "./auth-helpers";

test("username is empty initially and only a successful login is remembered", async ({
  page,
}) => {
  await page.goto("/login");
  const username = page.getByLabel("Login", { exact: true });
  await expect(username).toHaveValue("");
  await expect(page.locator("select")).toHaveCount(0);
  await username.fill("organizer");
  await page
    .getByLabel("Hasło", { exact: true })
    .fill("Wrong-test-passphrase-000");
  await page.getByRole("button", { name: "Wejdź na boisko" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.getItem("volleycrew:last-username")),
  ).toBeNull();
  await page
    .getByLabel("Hasło", { exact: true })
    .fill("Admin-test-passphrase-123");
  await page.getByRole("button", { name: "Wejdź na boisko" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await expect(
    page.getByText("Dobra ekipa, trochę ruchu i dwie godziny dla siebie."),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await expect(username).toHaveValue("organizer");
  await page.reload();
  await expect(username).toHaveValue("organizer");
  await expect(page.getByLabel("Hasło", { exact: true })).toHaveValue("");
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(
    "Admin-test-passphrase-123",
  );
});

test("admin can preview player screens and return from any route", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  await page.goto("/calendar");
  await page
    .getByRole("button", { name: "Dodaj spotkanie", exact: true })
    .click();
  for (const width of [360, 390, 430]) {
    await page.setViewportSize({ width, height: 844 });
    const form = page.locator(".plain-fieldset");
    await expect(form).toBeVisible();
    expect(
      await form.locator("input, button").evaluateAll((elements) =>
        elements.every((element) => {
          const box = element.getBoundingClientRect();
          const card = element.closest(".card")!.getBoundingClientRect();
          return box.left >= card.left && box.right <= card.right;
        }),
      ),
    ).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: info.outputPath("calendar-fixed.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Użytkownik", exact: true }).click();
  await expect(page.locator(".calendar-admin")).toHaveCount(0);
  await page.goto("/profile");
  await expect(
    page.getByRole("link", { name: "Ustawienia ekipy" }),
  ).toHaveCount(0);
  await page.goto("/admin/settings");
  await expect(
    page.getByRole("heading", { name: "Brak dostępu" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Administrator", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ustawienia ekipy" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Użytkownik", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await expect(page.locator(".room-panel")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Administrator", exact: true })
    .click();
  await page.goto("/calendar");
  await expect(page.locator(".calendar-admin")).toBeVisible();
});

test("installation uses the browser prompt and hides after installation", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(
    page.getByRole("button", { name: "Dodaj aplikację do telefonu" }),
  ).toBeVisible();
  await page.evaluate(() => {
    const event = new Event("beforeinstallprompt", { cancelable: true });
    Object.assign(event, {
      prompt: async () => {
        document.documentElement.dataset.installPrompted = "true";
        return { outcome: "accepted" };
      },
    });
    window.dispatchEvent(event);
  });
  await page
    .getByRole("button", { name: "Dodaj aplikację do telefonu" })
    .click();
  await expect(page.locator("html")).toHaveAttribute(
    "data-install-prompted",
    "true",
  );
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.evaluate(() => window.dispatchEvent(new Event("appinstalled")));
  await expect(
    page.getByRole("button", { name: "Dodaj aplikację do telefonu" }),
  ).toHaveCount(0);
});

test("installation offers platform instructions without a browser prompt", async ({
  page,
}, info) => {
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Dodaj aplikację do telefonu" })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  if (info.project.name === "webkit")
    await expect(
      dialog.getByText("Do ekranu początkowego", { exact: false }),
    ).toBeVisible();
  if (info.project.name === "mobile")
    await expect(dialog.getByText(/Zainstaluj aplikację/)).toBeVisible();
  await page.screenshot({
    path: info.outputPath("install-help.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "Rozumiem" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Dodaj aplikację do telefonu" }),
  ).toBeFocused();
});
