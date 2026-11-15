import { expect, test } from "./fixtures";
import { adminLogin } from "./auth-helpers";

test("invite, remembered session, private username login, profile, reset and blocking", async ({
  page,
  browser,
}, info) => {
  const nickname = `Misiek-${info.project.name}`;
  const username = `misiek-${info.project.name}`;
  await page.goto(`/join?token=${process.env.E2E_INVITE}&fbclid=tracking#_=_`);
  await expect(page).toHaveURL(/\/join$/);
  await page.getByLabel("Imię", { exact: true }).fill("Michał");
  await page.getByLabel("Nazwisko", { exact: true }).fill("Nowak");
  await page.getByLabel("Przydomek (opcjonalnie)").fill(nickname);
  await page.getByLabel("Login", { exact: true }).fill(username);
  await page.getByLabel("Twoje hasło", { exact: true }).fill("abcdefgh");
  await page.getByLabel("Powtórz hasło", { exact: true }).fill("abcdefgh");
  await page.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await page.goto("/profile");
  await expect(page.getByText("Twój status: Gość")).toBeVisible();
  await page.getByLabel("Przydomek (opcjonalnie)").fill(nickname + "-nowy");
  await page.getByRole("button", { name: "Zapisz dane" }).click();
  await expect(page.getByText("Dane zostały zapisane.")).toBeVisible();
  await page.screenshot({
    path: info.outputPath("profile.png"),
    fullPage: true,
    scale: "css",
  });
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await expect(
    page.getByRole("heading", { name: "Dobrze Cię widzieć" }),
  ).toBeVisible();
  await expect(page.getByLabel("Login", { exact: true })).toHaveValue(username);
  expect(await page.locator("body").innerText()).not.toContain("Nowak");
  await page.screenshot({
    path: info.outputPath("login.png"),
    fullPage: true,
    scale: "css",
  });
  await page.getByLabel("Login", { exact: true }).fill(username);
  await page.getByLabel("Hasło", { exact: true }).fill("abcdefgh");
  await page.getByRole("button", { name: "Wejdź na boisko" }).click();
  await expect(
    page.getByRole("heading", { name: "Mój profil", exact: true }),
  ).toBeVisible();
  await page.goto("/admin/settings");
  await expect(
    page.getByRole("heading", { name: "Brak dostępu" }),
  ).toBeVisible();
  const admin = await browser.newContext({
    viewport: page.viewportSize() ?? undefined,
  });
  await adminLogin(admin);
  const adminPage = await admin.newPage();
  await adminPage.goto("/admin/settings");
  const row = adminPage
    .getByRole("listitem")
    .filter({ hasText: `${nickname}-nowy` });
  await row.getByRole("button", { name: "Reset hasła" }).click();
  const url = await adminPage.getByLabel("Link do przekazania").inputValue();
  await page.goto(url);
  await expect(page).toHaveURL(/\/reset-password$/);
  await page.getByLabel("Login", { exact: true }).fill(username);
  await page.getByLabel("Nowe hasło", { exact: true }).fill("12345678");
  await page.getByLabel("Powtórz nowe hasło", { exact: true }).fill("12345678");
  await page.getByRole("button", { name: "Ustaw nowe hasło" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await row.getByRole("button", { name: "Zablokuj", exact: true }).click();
  await adminPage
    .getByRole("button", { name: "Potwierdź", exact: true })
    .click();
  await expect(row.getByText("Gość · Profil zablokowany")).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Dobrze Cię widzieć" }),
  ).toBeVisible();
  await adminPage.screenshot({
    path: info.outputPath("admin.png"),
    fullPage: true,
    scale: "css",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await adminPage.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const createdInviteResponse = adminPage.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/admin/invites") &&
      response.request().method() === "POST",
  );
  await adminPage
    .getByRole("button", { name: "Utwórz link z zaproszeniem" })
    .click();
  await expect(adminPage.getByLabel("Link do przekazania")).toHaveValue(
    /\/join\?token=/,
  );
  const inviteUrl = await adminPage
    .getByLabel("Link do przekazania")
    .inputValue();
  const createdInvite = await (await createdInviteResponse).json();
  const inviteRow = adminPage.getByTestId(`invite-${createdInvite.id}`);
  const revoked = adminPage.waitForResponse(
    (response) =>
      response.url().endsWith(`/invites/${createdInvite.id}/revoke`) &&
      response.request().method() === "POST",
  );
  await inviteRow
    .getByRole("button", { name: "Unieważnij", exact: true })
    .click();
  expect((await revoked).ok()).toBe(true);
  await expect(inviteRow.getByText(/Unieważnione/)).toBeVisible();
  await page.goto(inviteUrl);
  await page.getByLabel("Imię", { exact: true }).fill("Test");
  await page.getByLabel("Nazwisko", { exact: true }).fill("Odrzucony");
  await page
    .getByLabel("Login", { exact: true })
    .fill(`member-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`);
  await page.getByLabel("Twoje hasło", { exact: true }).fill("abcdefgh");
  await page.getByLabel("Powtórz hasło", { exact: true }).fill("abcdefgh");
  await page.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Link jest nieprawidłowy, wygasł lub został wykorzystany.",
  );
  await admin.close();
});
