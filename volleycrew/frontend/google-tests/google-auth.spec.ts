import type { Page } from "@playwright/test";
import { expect, test } from "../e2e/fixtures";

async function google(
  page: Page,
  subject = "browser-google-account",
  cancelled = false,
) {
  await page.route(
    "https://accounts.google.com/o/oauth2/v2/auth?**",
    async (route) => {
      const params = new URL(route.request().url()).searchParams;
      const callback = new URL(params.get("redirect_uri")!);
      callback.searchParams.set("state", params.get("state")!);
      if (cancelled) callback.searchParams.set("error", "access_denied");
      else
        callback.searchParams.set(
          "code",
          Buffer.from(
            JSON.stringify({
              sub: subject,
              nonce: params.get("nonce"),
              challenge: params.get("code_challenge"),
            }),
          ).toString("base64url"),
        );
      // WebKit's interception API cannot fulfill a redirect. A local issuer page
      // performs the same top-level cross-origin return to the real callback.
      await route.fulfill({
        contentType: "text/html",
        body: `<script>location.replace(${JSON.stringify(callback.href)})</script>`,
      });
    },
  );
}

test("connect Google with PIN, log in through Google and disconnect", async ({
  page,
  context,
}, info) => {
  await google(page, `google-account-${info.project.name}`);
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await page.getByLabel("Imię", { exact: true }).fill("Google");
  await page
    .getByLabel("Nazwisko", { exact: true })
    .fill(`Test-${info.project.name}`);
  await page.getByLabel("Twój PIN", { exact: true }).fill("654321");
  await page.getByLabel("Powtórz PIN", { exact: true }).fill("654321");
  await page.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  const player = await (await context.request.get("/api/v1/me")).json();
  await page.goto("/profile");
  await page.getByLabel("PIN potwierdzający zmianę").fill("654321");
  await page.getByRole("button", { name: "Połącz konto Google" }).click();
  await expect(
    page.getByRole("button", { name: "Odłącz konto Google" }),
  ).toBeVisible();
  await expect(
    page.getByText("Konto Google zostało połączone z Twoim profilem."),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/profile$/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("google-profile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await page.screenshot({
    path: info.outputPath("google-login.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Zaloguj przez Google" }).click();
  await expect(
    page.getByRole("heading", { name: "Mój profil", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/profile$/);
  const signedIn = await (await context.request.get("/api/v1/me")).json();
  expect(signedIn.id).toBe(player.id);
  expect(signedIn.role).toBe("player");
  await page.getByLabel("PIN potwierdzający zmianę").fill("654321");
  await page.getByRole("button", { name: "Odłącz konto Google" }).click();
  await expect(
    page.getByRole("button", { name: "Połącz konto Google" }),
  ).toBeVisible();
  await expect(
    page.getByText("Konto Google zostało odłączone. Pozostałe sesje wygasły."),
  ).toBeVisible();
});

test("Google cancellation and unlinked accounts keep PIN login available", async ({
  page,
}) => {
  await google(page, "unlinked-browser-account");
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole("button", { name: "Zaloguj przez Google" }).click();
  await expect(
    page.getByText(/To konto Google nie jest połączone/),
  ).toBeVisible();
  await expect(page.getByLabel("PIN", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
  await page.unroute("https://accounts.google.com/o/oauth2/v2/auth?**");
  await google(page, "unlinked-browser-account", true);
  await page.getByRole("button", { name: "Zaloguj przez Google" }).click();
  await expect(
    page.getByText(/Logowanie Google zostało anulowane/),
  ).toBeVisible();
});
