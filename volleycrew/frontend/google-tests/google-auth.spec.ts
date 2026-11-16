import type { Page } from "@playwright/test";
import { expect, test } from "../e2e/fixtures";

// Exercise the real admission limits. A fast automated multi-login flow must
// honor Retry-After and retry the rejected click as a user would; never reset
// the production limiter or silently retry an accepted mutation.
async function authClick(page: Page, name: string) {
  const click = async () => {
    const response = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        /\/api\/v1\/(auth\/(google\/(start|register)|register|login)|me\/google\/password)$/.test(
          new URL(r.url()).pathname,
        ),
    );
    await page.getByRole("button", { name, exact: true }).click();
    return await response;
  };
  let response = await click();
  if (response.status() === 429) {
    await expect(page.getByRole("alert")).toContainText("Za dużo prób");
    const retry = Number(response.headers()["retry-after"]);
    expect(retry).toBeGreaterThan(0);
    // The limiter uses server time, which the browser's mocked clock cannot advance.
    await new Promise((resolve) => setTimeout(resolve, (retry + 0.1) * 1000));
    response = await click();
  }
  expect(response.ok()).toBe(true);
}

async function google(
  page: Page,
  subject = "browser-google-account",
  cancelled = false,
  names = { given_name: "Google", family_name: "Testowy" },
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
              ...names,
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

test("connect Google with a password, log in through Google and disconnect", async ({
  page,
  context,
}, info) => {
  await google(page, `google-account-${info.project.name}`);
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await page.getByLabel("Imię", { exact: true }).fill("Google");
  await page
    .getByLabel("Nazwisko", { exact: true })
    .fill(`Test-${info.project.name}`);
  await page
    .getByLabel("Login", { exact: true })
    .fill(`member-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`);
  await page
    .getByLabel("Twoje hasło", { exact: true })
    .fill("Player-test-passphrase-456");
  await page
    .getByLabel("Powtórz hasło", { exact: true })
    .fill("Player-test-passphrase-456");
  await authClick(page, "Dołączam do gry");
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  const player = await (await context.request.get("/api/v1/me")).json();
  await page.goto("/profile");
  await page
    .getByLabel("Hasło potwierdzające zmianę", { exact: true })
    .fill("Player-test-passphrase-456");
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
  await authClick(page, "Zaloguj przez Google");
  await expect(
    page.getByRole("heading", { name: "Mój profil", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/profile$/);
  const signedIn = await (await context.request.get("/api/v1/me")).json();
  expect(signedIn.id).toBe(player.id);
  expect(signedIn.role).toBe("player");
  await page
    .getByLabel("Hasło potwierdzające zmianę", { exact: true })
    .fill("Player-test-passphrase-456");
  await page.getByRole("button", { name: "Odłącz konto Google" }).click();
  await expect(
    page.getByRole("button", { name: "Połącz konto Google" }),
  ).toBeVisible();
  await expect(
    page.getByText("Konto Google zostało odłączone. Pozostałe sesje wygasły."),
  ).toBeVisible();
});

test("Google cancellation and unlinked accounts keep password login available", async ({
  page,
}) => {
  await google(page, "unlinked-browser-account");
  await page.goto("/profile");
  await expect(page).toHaveURL(/\/login$/);
  await authClick(page, "Zaloguj przez Google");
  await expect(
    page.getByText(/To konto Google nie jest połączone/),
  ).toBeVisible();
  await expect(page.getByLabel("Hasło", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
  await page.unroute("https://accounts.google.com/o/oauth2/v2/auth?**");
  await google(page, "unlinked-browser-account", true);
  await authClick(page, "Zaloguj przez Google");
  await expect(
    page.getByText(/Logowanie Google zostało anulowane/),
  ).toBeVisible();
});

test("invite Google join offers editable names, creates no password and can add one later", async ({
  page,
  context,
}, info) => {
  test.setTimeout(60_000);
  const subject = `invited-${info.project.name}`;
  await google(page, subject, false, {
    given_name: "Imię z Google",
    family_name: "Nazwisko z Google",
  });
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await expect(page).toHaveURL(/\/join$/);
  await authClick(page, "Dołącz przez Google");
  await expect(
    page.getByRole("heading", { name: "Sprawdź dane i dołącz" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/join\/google$/);
  await expect(page.getByLabel("Imię", { exact: true })).toHaveValue(
    "Imię z Google",
  );
  await expect(page.getByLabel("Nazwisko", { exact: true })).toHaveValue(
    "Nazwisko z Google",
  );
  await expect(page.getByLabel("Login", { exact: true })).toHaveCount(0);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  const anonymous = await context.request.get("/api/v1/me");
  expect(anonymous.status()).toBe(401);
  await page.getByLabel("Imię", { exact: true }).fill("Anna");
  await page
    .getByLabel("Nazwisko", { exact: true })
    .fill(`Poprawione-${info.project.name}`);
  await page
    .getByLabel("Przydomek (opcjonalnie)")
    .fill(`SSO-${info.project.name}`);
  await page.screenshot({
    path: info.outputPath("google-join-edit.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await authClick(page, "Dołączam do gry");
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  const player = await (await context.request.get("/api/v1/me")).json();
  expect(player).toMatchObject({
    first_name: "Anna",
    last_name: `Poprawione-${info.project.name}`,
    role: "player",
    priority_status: "guest",
    has_password: false,
    username: null,
  });
  await page.goto("/profile");
  await expect(
    page.getByRole("button", { name: "Odłącz konto Google" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Google jest Twoją jedyną metodą logowania.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await authClick(page, "Zaloguj przez Google");
  await expect(
    page.getByRole("heading", { name: "Mój profil", exact: true }),
  ).toBeVisible();
  expect((await (await context.request.get("/api/v1/me")).json()).id).toBe(
    player.id,
  );
  await authClick(page, "Ustaw login i hasło");
  await expect(page).toHaveURL(/\/profile\/password$/);
  await expect(
    page.getByRole("heading", { name: "Ustaw login i hasło" }),
  ).toBeVisible();
  await page
    .getByLabel("Login", { exact: true })
    .fill(`sso-${info.project.name}`);
  await page
    .getByLabel("Nowe hasło", { exact: true })
    .fill("Optional-password-from-Google");
  await page
    .getByLabel("Powtórz nowe hasło", { exact: true })
    .fill("Optional-password-from-Google");
  await authClick(page, "Zapisz login i hasło");
  await expect(page).toHaveURL(/\/profile$/);
  await expect(
    page.getByRole("heading", { name: "Zmiana hasła" }),
  ).toBeVisible();
  const after = await (await context.request.get("/api/v1/me")).json();
  expect(after).toMatchObject({
    id: player.id,
    username: `sso-${info.project.name}`,
    has_password: true,
  });
  await page
    .getByLabel("Hasło potwierdzające zmianę", { exact: true })
    .fill("Optional-password-from-Google");
  await page.getByRole("button", { name: "Odłącz konto Google" }).click();
  await expect(
    page.getByRole("button", { name: "Połącz konto Google" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Wyloguj" }).click();
  await page
    .getByLabel("Login", { exact: true })
    .fill(`sso-${info.project.name}`);
  await page
    .getByLabel("Hasło", { exact: true })
    .fill("Optional-password-from-Google");
  await authClick(page, "Wejdź na boisko");
  await expect(
    page.getByRole("heading", { name: "Mój profil", exact: true }),
  ).toBeVisible();
});

test("Google join completion token leaves the URL and must be restarted after reload", async ({
  page,
}, info) => {
  await google(page, `reload-${info.project.name}`);
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await authClick(page, "Dołącz przez Google");
  await expect(page.getByLabel("Imię", { exact: true })).toHaveValue("Google");
  await expect(page).toHaveURL(/\/join\/google$/);
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Otwórz ponownie link zaproszenia",
  );
  await expect(
    page.getByRole("button", { name: "Dołączam do gry" }),
  ).toHaveCount(0);
});
