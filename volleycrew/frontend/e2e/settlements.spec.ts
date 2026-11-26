import {
  devices,
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import { adminLogin } from "./auth-helpers";
import { audit } from "./ui-helpers";

type Fixture = {
  first: string;
  second: string;
  payer: string;
  payer_id: string;
  first_id: string;
  second_id: string;
  exact: string;
  free: string;
  no_cost: string;
  correction: string;
  cancelled: string;
  charges: string[];
  series_start: string;
};

function fixture(project: string): Fixture {
  return JSON.parse(process.env.E2E_SETTLEMENTS!)[project];
}

async function playerContext(
  browser: Browser,
  username: string,
  project: string,
) {
  const device =
    project === "webkit"
      ? devices["iPhone 13"]
      : project === "mobile"
        ? devices["Pixel 7"]
        : devices["Desktop Chrome"];
  const context = await browser.newContext({
    ...device,
    baseURL: "http://127.0.0.1:5175",
    locale: "pl-PL",
    timezoneId: "Europe/Warsaw",
  });
  const csrf = await context.request.get("/api/v1/auth/csrf");
  const response = await context.request.post("/api/v1/auth/login", {
    headers: {
      Origin: "http://127.0.0.1:5175",
      "X-CSRF-Token": (await csrf.json()).token,
    },
    data: { username, password: "Admin-test-passphrase-123" },
  });
  expect(response.ok()).toBe(true);
  return context;
}

const pln = (grosz: number) =>
  new Intl.NumberFormat("pl-PL", {
    style: "currency",
    currency: "PLN",
  }).format(grosz / 100);

function card(page: Page, owner: string) {
  return page
    .locator(".settlement-card")
    .filter({ has: page.getByRole("heading", { name: owner, exact: true }) });
}

async function balances(page: Page, owner: string, amounts: number[]) {
  await expect(card(page, owner).locator("dd")).toHaveText(amounts.map(pln));
}

async function picked(page: Page, ...ids: string[]) {
  for (const id of ids)
    await page.locator(`button[data-charge-id="${id}"]`).click();
}

function atWeek(value: string, week: number) {
  const date = new Date(value + "T12:00:00Z");
  date.setUTCDate(date.getUTCDate() + 7 * week);
  return date.toISOString().slice(0, 10);
}

async function showAttendance(page: Page, id: string, absent?: string) {
  await page.goto(`/meetings/${id}`);
  const panel = page.getByRole("region", {
    name: "Panel organizatora",
    exact: true,
  });
  await panel
    .getByRole("button", { name: "Wszyscy obecni", exact: true })
    .click();
  if (absent) {
    await panel
      .locator(".attendance-list li")
      .filter({ hasText: absent })
      .getByRole("button", { name: "Nieobecny/a", exact: true })
      .click();
  }
  await panel.getByRole("button", { name: "Zapisz szkic obecności" }).click();
  await panel
    .getByRole("button", { name: "Zatwierdź obecność", exact: true })
    .click();
  return panel;
}

async function pay(page: Page, ...ids: string[]) {
  await picked(page, ...ids);
  const allSelected =
    (await page.locator("button[data-charge-id]").count()) === ids.length;
  await page
    .getByRole("button", {
      name: allSelected ? /Zapłać wszystko/ : /Przejdź do płatności/,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Płatność", exact: true });
  await dialog
    .getByRole("button", { name: "Zgłoś wpłatę", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByText("Wpłata zgłoszona do potwierdzenia."),
  ).toBeVisible();
}

async function adminReview(
  page: Page,
  name: string,
  decision: "paid" | "rejected",
) {
  await page.goto("/admin/settlements");
  const account = card(page, name);
  await account.getByText("Historia wpłat", { exact: true }).click();
  if (decision === "paid") {
    await account.getByRole("button", { name: "Potwierdź wpływ" }).click();
  } else {
    await account.getByRole("button", { name: "Odrzuć zgłoszenie" }).click();
    await account
      .getByLabel("Powód odrzucenia")
      .fill("Wpłaty nie ma na rachunku");
    await account.getByRole("button", { name: "Potwierdź odrzucenie" }).click();
  }
  await expect(account.getByText("Zapisano decyzję o wpłacie.")).toBeVisible();
}

async function seriesRule(context: BrowserContext, date: string) {
  const response = await context.request.get("/api/v1/admin/schedule");
  expect(response.ok()).toBeTruthy();
  return (await response.json()).rules.find(
    (rule: { effective_from: string }) => rule.effective_from === date,
  );
}

test.describe("meeting settlements", () => {
  test.describe.configure({ timeout: 60_000 });

  test("series pricing and one-off venue and price overrides", async ({
    page,
    context,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const first = seed.series_start;
    const middle = atWeek(first, 1);
    const last = atWeek(first, 2);
    await page.goto(`/calendar?month=${first.slice(0, 7)}`);
    await page.getByRole("button", { name: "Zaplanuj serię" }).click();
    await page.getByLabel("Zmiana od dnia").fill(first);
    await page.getByLabel("Dzień tygodnia").selectOption("1");
    await page.getByLabel("Do dnia (włącznie, opcjonalnie)").fill(last);
    await page.getByLabel("Koszt spotkania (PLN)").fill("200,00");
    await page
      .getByRole("button", { name: "Pokaż podgląd harmonogramu" })
      .click();
    await page.getByRole("button", { name: "Zatwierdź harmonogram" }).click();
    await expect(page.getByText(/Harmonogram zapisany/)).toBeVisible();
    const series = await seriesRule(context, first);
    expect(series.cost_grosz).toBe(20000);
    const player = await playerContext(browser, seed.first, info.project.name);
    try {
      const slot = await (
        await player.request.post("/api/v1/meetings/resolve", {
          headers: {
            Origin: "http://127.0.0.1:5175",
            "X-CSRF-Token": (
              await (await player.request.get("/api/v1/auth/csrf")).json()
            ).token,
          },
          data: { schedule_version_id: series.id, source_date: middle },
        })
      ).json();
      const member = await player.newPage();
      await member.goto(`/meetings/${slot.id}`);
      await member
        .getByRole("button", { name: "Potwierdzam obecność" })
        .click();
      await expect(
        member.getByRole("heading", { name: "Masz miejsce na boisku" }),
      ).toBeVisible();
      await page.goto(`/meetings/${slot.id}`);
      async function edit(label: string, value: string) {
        await page.getByRole("button", { name: "Edytuj to spotkanie" }).click();
        await page.getByLabel(label, { exact: true }).fill(value);
        await page.getByRole("button", { name: "Pokaż podgląd zmian" }).click();
        await page
          .getByRole("button", { name: "Zapisz zmiany spotkania" })
          .click();
      }
      await edit("Koszt spotkania (PLN)", "240");
      await expect(page.locator(".hero-date").locator("..")).toContainText(
        pln(24000),
      );
      await member.reload();
      await expect(
        member.getByRole("heading", { name: "Masz miejsce na boisku" }),
      ).toBeVisible();
      await page.reload();
      await edit("Miejsce spotkania", "Sala zastępcza");
      await expect(page.getByText(/Termin zmieniony\./)).toBeVisible();
      await member.reload();
      await expect(
        member.getByRole("button", { name: /Potwierdzam nowy termin/ }),
      ).toBeVisible();

      await page.goto(`/calendar?month=${first.slice(0, 7)}`);
      const ruleCard = page.getByTestId(`series-${series.id}`);
      await ruleCard.getByRole("button", { name: "Edytuj serię" }).click();
      await page.getByLabel("Koszt spotkania (PLN)").fill("220");
      await page
        .getByRole("button", { name: "Pokaż podgląd harmonogramu" })
        .click();
      await page.getByRole("button", { name: "Zatwierdź harmonogram" }).click();
      await expect(page.getByText("Seria została zmieniona.")).toBeVisible();
      const data = await (
        await context.request.get(
          `/api/v1/calendar?from=${first}&to=${atWeek(first, 3)}`,
        )
      ).json();
      expect(
        data.items
          .slice(0, 3)
          .map((item: { cost_grosz: number }) => item.cost_grosz),
      ).toEqual([22000, 24000, 22000]);
      expect(data.items[1]).toMatchObject({
        id: slot.id,
        venue: "Sala zastępcza",
      });
    } finally {
      await player.close();
    }
  });

  test("actual attendance splits to the grosz and retries after a lost response", async ({
    page,
    context,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const panel = await showAttendance(page, seed.exact, "Alicja");
    const split = panel.getByRole("list", { name: "Podział kosztu" });
    await expect(split.getByText(pln(1667), { exact: false })).toHaveCount(8);
    await expect(split.getByText(pln(1666), { exact: false })).toHaveCount(4);
    const url = `**/api/v1/admin/meetings/${seed.exact}/attendance/confirm`;
    await page.route(url, async (route) => {
      expect((await route.fetch()).ok()).toBe(true);
      await route.abort();
    });
    await panel
      .getByRole("button", { name: "Potwierdź sprawdzoną obecność" })
      .click();
    await expect(
      panel.getByRole("button", { name: "Ponów tę operację" }),
    ).toBeVisible();
    await page.unroute(url);
    await panel.getByRole("button", { name: "Ponów tę operację" }).click();
    await expect(
      panel.getByRole("button", { name: "Ponów tę operację" }),
    ).toHaveCount(0);
    const dashboard = await (
      await context.request.get("/api/v1/admin/settlements")
    ).json();
    const shares = dashboard.flatMap(
      (account: { charges: { meeting_id: string; amount: number }[] }) =>
        account.charges
          .filter((charge) => charge.meeting_id === seed.exact)
          .map((charge) => charge.amount),
    );
    expect(shares.sort()).toEqual([
      ...Array(4).fill(1666),
      ...Array(8).fill(1667),
    ]);
    expect(
      dashboard.find(
        (row: { player_id: string }) => row.player_id === seed.first_id,
      ).due,
    ).toBe(9000);
  });

  test("free and canceled meetings create no charges", async ({
    page,
    context,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    for (const id of [seed.free, seed.no_cost]) {
      const panel = await showAttendance(page, id);
      await expect(
        panel.getByRole("list", { name: "Podział kosztu" }),
      ).toHaveCount(0);
      await panel
        .getByRole("button", { name: "Potwierdź sprawdzoną obecność" })
        .click();
      await expect(panel.getByText("Korekta kosztu spotkania")).toBeVisible();
    }
    await page.goto(`/meetings/${seed.cancelled}`);
    await page.getByRole("button", { name: "Odwołaj spotkanie" }).click();
    await page.getByRole("button", { name: "Potwierdzam odwołanie" }).click();
    await expect(
      page.getByText(/Spotkanie odwołane\. Poinformuj/),
    ).toBeVisible();
    const data = await (
      await context.request.get("/api/v1/admin/settlements")
    ).json();
    expect(
      data
        .flatMap((row: { charges: { meeting_id: string }[] }) => row.charges)
        .some((item: { meeting_id: string }) =>
          [seed.free, seed.no_cost, seed.cancelled].includes(item.meeting_id),
        ),
    ).toBe(false);
  });

  test("one transfer settles multiple charges and concurrent reviews are idempotent", async ({
    page,
    context,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const player = await playerContext(browser, seed.first, info.project.name);
    const secondTab = await context.newPage();
    try {
      const member = await player.newPage();
      await member.goto("/settlements");
      await balances(member, "Moje saldo", [9000, 0]);
      const table = member.getByRole("table", { name: "Opłaty za spotkania" });
      await expect(table.getByRole("checkbox")).toHaveCount(0);
      const first = member.locator(
        `button[data-charge-id="${seed.charges[0]}"]`,
      );
      const firstRow = table.getByRole("row").filter({ has: first });
      await firstRow
        .getByRole("cell", { name: pln(4000), exact: true })
        .click();
      await expect(first).toHaveAttribute("aria-pressed", "true");
      await expect(firstRow).toHaveAttribute("data-selected", "true");

      const payAll = member.getByRole("button", { name: /Zapłać wszystko/ });
      const paySelected = member.getByRole("button", {
        name: /Przejdź do płatności/,
      });
      await paySelected.click();
      await expect(
        member.getByRole("dialog").getByText(/Wybrana kwota.*40,00/),
      ).toBeVisible();
      await member.keyboard.press("Escape");
      await member
        .getByRole("button", { name: "Zamknij bez zgłoszenia" })
        .click();
      await expect(paySelected).toBeFocused();
      await payAll.click();
      await expect(
        member.locator('.settlement-table tr[data-selected="true"]'),
      ).toHaveCount(3);
      const payment = member.getByRole("dialog", {
        name: "Płatność",
        exact: true,
      });
      const total = payment.getByText(/Wybrana kwota.*90,00/);
      await expect(total).toBeFocused();
      await member.keyboard.press("Escape");
      const closePrompt = member.getByRole("dialog", {
        name: "Zamknąć bez zgłoszenia?",
      });
      await expect(
        closePrompt.getByRole("button", { name: "Wróć do płatności" }),
      ).toBeFocused();
      await closePrompt
        .getByRole("button", { name: "Wróć do płatności" })
        .click();
      await expect(total).toBeVisible();
      await member.keyboard.press("Escape");
      await expect(closePrompt).toBeVisible();
      await member.keyboard.press("Escape");
      await expect(member.getByRole("dialog")).toHaveCount(0);
      await expect(payAll).toBeFocused();
      await payAll.click();
      await expect(total).toBeVisible();
      await payment
        .getByRole("button", { name: "Zamknij", exact: true })
        .click();
      await closePrompt
        .getByRole("button", { name: "Zamknij bez zgłoszenia" })
        .click();
      await expect(closePrompt).toHaveCount(0);
      await expect(payAll).toBeFocused();
      await balances(member, "Moje saldo", [9000, 0]);

      const last = table.locator(`button[data-charge-id="${seed.charges[2]}"]`);
      await expect(paySelected).toHaveCount(0);
      await expect(payAll).toBeVisible();
      await last.press("Space");
      await expect(last).toHaveAttribute("aria-pressed", "false");
      await expect(table.locator('tr[data-selected="true"]')).toHaveCount(2);
      await last.press("Space");
      await expect(table.locator('tr[data-selected="true"]')).toHaveCount(3);
      await expect(paySelected).toHaveCount(0);
      await last.press("Space");
      await paySelected.click();
      await expect(payment.getByText(/Wybrana kwota.*70,00/)).toBeVisible();
      await payment
        .getByRole("button", { name: "Zgłoś wpłatę", exact: true })
        .click();
      await expect(payment).toHaveCount(0);
      await balances(member, "Moje saldo", [2000, 7000]);
      const name = `Alicja Rozliczenia ${info.project.name}`;
      await Promise.all([
        page.goto("/admin/settlements"),
        secondTab.goto("/admin/settlements"),
      ]);
      const summary = page.getByRole("table", {
        name: "Podsumowanie rozliczeń",
      });
      const totalCells = summary.locator("tfoot").getByRole("cell");
      const summaryRow = summary.getByRole("row", { name: new RegExp(name) });
      await expect(summaryRow.getByRole("cell")).toHaveText([
        pln(2000),
        pln(7000),
        pln(0),
      ]);
      const [teamDue, teamPending, teamPaid] = (
        await totalCells.allTextContents()
      ).map((value) => Number(value.replace(/[^0-9-]/g, "")));
      const playerDetails = summaryRow.getByRole("link", { name, exact: true });
      await playerDetails.click();
      await expect(
        card(page, name).getByRole("heading", { name, exact: true }),
      ).toBeFocused();
      await expect(
        card(page, name).getByRole("table", { name: "Opłaty za spotkania" }),
      ).toBeVisible();
      await expect(card(page, name).locator("details[open]")).toHaveCount(0);
      await Promise.all(
        [page, secondTab].map((admin) =>
          card(admin, name)
            .getByText("Historia wpłat", { exact: true })
            .click(),
        ),
      );
      const pendingReport = card(page, name)
        .locator(".settlement-list li")
        .filter({
          has: page.getByRole("button", { name: "Potwierdź wpływ" }),
        });
      await expect(pendingReport).toBeVisible();
      expect(
        await pendingReport.evaluate((row) => {
          const description = row.querySelector(
            ".settlement-report-description",
          )!;
          const actions = row.querySelector(".settlement-review-actions")!;
          return (
            actions.getBoundingClientRect().top -
            description.getBoundingClientRect().bottom
          );
        }),
      ).toBeGreaterThanOrEqual(8);
      await Promise.all(
        [page, secondTab].map((admin) =>
          card(admin, name)
            .getByRole("button", { name: "Potwierdź wpływ" })
            .click(),
        ),
      );
      await expect(summaryRow.getByRole("cell")).toHaveText([
        pln(2000),
        pln(0),
        pln(7000),
      ]);
      await expect(totalCells).toHaveText([
        pln(teamDue),
        pln(teamPending - 7000),
        pln(teamPaid + 7000),
      ]);
      await member.reload();
      await balances(member, "Moje saldo", [2000, 0]);
      await expect(member.locator("details[open]")).toHaveCount(0);
      await member.getByText("Historia wpłat", { exact: true }).click();
      await expect(
        member
          .locator("details")
          .filter({ hasText: "Historia wpłat" })
          .getByText(/70,00.*Opłacone/),
      ).toHaveCount(1);
    } finally {
      await Promise.all([player.close(), secondTab.close()]);
    }
  });

  test("rejected transfer returns to the balance and can be reported again", async ({
    page,
    context,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const player = await playerContext(browser, seed.second, info.project.name);
    try {
      const member = await player.newPage();
      await member.goto("/settlements");
      await pay(member, seed.charges[5]);
      await adminReview(
        page,
        `Bartek Rozliczenia ${info.project.name}`,
        "rejected",
      );
      await member.reload();
      await member.getByText("Historia wpłat", { exact: true }).click();
      await expect(member.getByText(/Wpłaty nie ma na rachunku/)).toBeVisible();
      await balances(member, "Moje saldo", [11001, 0]);
      await pay(member, seed.charges[5]);
      await balances(member, "Moje saldo", [10501, 500]);
      await adminReview(
        page,
        `Bartek Rozliczenia ${info.project.name}`,
        "rejected",
      );
    } finally {
      await player.close();
    }
  });

  test("payment details, clipboard, Revolut destination and private access", async ({
    page,
    context,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const player = await playerContext(browser, seed.first, info.project.name);
    const another = await playerContext(
      browser,
      seed.second,
      info.project.name,
    );
    try {
      if (browser.browserType().name() === "chromium") {
        await player.grantPermissions(["clipboard-read", "clipboard-write"]);
      }
      const member = await player.newPage();
      const other = await another.newPage();
      await page.goto("/profile");
      await page.getByLabel("Numer telefonu BLIK").fill("+48 500 600 700");
      await page
        .getByLabel("Link Revolut.me")
        .fill("https://revolut.me/volleycrew-test");
      await page.getByRole("button", { name: "Zapisz metody wpłat" }).click();
      await expect(page.getByText("Dane do wpłat zapisane.")).toBeVisible();
      const paymentSettings = page.getByRole("form", { name: "Dane do wpłat" });
      await page
        .getByRole("button", { name: "Użytkownik", exact: true })
        .click();
      await expect(paymentSettings).toHaveCount(0);
      await page
        .getByRole("button", { name: "Administrator", exact: true })
        .click();
      await expect(paymentSettings).toBeVisible();
      await member.goto("/profile");
      await expect(
        member.getByRole("form", { name: "Dane do wpłat" }),
      ).toHaveCount(0);
      const settingsPath = "/api/v1/me/payment-details";
      const csrf = await (await player.request.get("/api/v1/auth/csrf")).json();
      const [read, write] = await Promise.all([
        player.request.get(settingsPath),
        player.request.put(settingsPath, {
          headers: {
            Origin: "http://127.0.0.1:5175",
            "X-CSRF-Token": csrf.token,
          },
          data: { blik_phone: "+48500600700", revolut_link: null },
        }),
      ]);
      expect(read.status()).toBe(403);
      expect(write.status()).toBe(403);
      const menu = member.getByRole("navigation", {
        name:
          info.project.name === "desktop" ? "Menu główne" : "Nawigacja mobilna",
      });
      const settlements = menu.getByRole("link", {
        name: "Rozliczenia",
        exact: true,
      });
      await settlements.click();
      await expect(settlements).toHaveAttribute("aria-current", "page");
      await expect(
        member
          .getByRole("table", { name: "Opłaty za spotkania" })
          .getByRole("columnheader"),
      ).toHaveText(["Spotkanie", "Kwota", "Status"]);
      const before = await (
        await player.request.get("/api/v1/me/settlements")
      ).json();
      expect(await audit(member)).toEqual([]);
      const payAll = member.getByRole("button", { name: /Zapłać wszystko/ });
      await payAll.click();
      const dialog = member.getByRole("dialog", {
        name: "Płatność",
        exact: true,
      });
      const revolut = dialog.getByRole("link", { name: "Otwórz Revolut" });
      const gap = await dialog.evaluate((element) => {
        const methods = element.querySelector(".settlement-payment-methods")!;
        const submit = element.querySelector(
          ".settlement-payment-submit button",
        )!;
        return (
          submit.getBoundingClientRect().top -
          methods.getBoundingClientRect().bottom
        );
      });
      expect(gap).toBeGreaterThan(16);
      await expect(revolut).toHaveAttribute(
        "href",
        "https://revolut.me/volleycrew-test",
      );
      await player.route("https://revolut.me/volleycrew-test", (route) =>
        route.fulfill({ body: "Test destination" }),
      );
      await member.bringToFront();
      await member.getByRole("button", { name: "Kopiuj numer BLIK" }).click();
      await expect(member.getByText("Numer skopiowany.")).toBeVisible();
      await member.evaluate(() => {
        const testField = document.createElement("input");
        testField.setAttribute("aria-label", "Test schowka");
        document.querySelector("dialog[open]")!.append(testField);
      });
      const input = member.getByRole("textbox", { name: "Test schowka" });
      await input.press(process.platform === "darwin" ? "Meta+v" : "Control+v");
      await expect(input).toHaveValue("+48500600700");
      await input.evaluate((element) => element.remove());
      const [popup] = await Promise.all([
        player.waitForEvent("page"),
        revolut.click(),
      ]);
      await expect(popup.locator("body")).toHaveText("Test destination");
      await popup.close();
      await balances(member, "Moje saldo", [before.due, before.pending]);
      expect(await audit(member)).toEqual([]);
      expect(
        await member.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await member.screenshot({
        path: info.outputPath("payment-options.png"),
        fullPage: true,
        scale: "css",
      });
      await page.getByLabel("Link Revolut.me").fill("");
      await page.getByRole("button", { name: "Zapisz metody wpłat" }).click();
      await expect(page.getByText("Dane do wpłat zapisane.")).toBeVisible();
      await member.reload();
      await payAll.click();
      await expect(dialog).toBeVisible();
      await expect(revolut).toHaveCount(0);
      await other.goto("/settlements");
      await expect(
        other.locator(`button[data-charge-id="${seed.charges[2]}"]`),
      ).toHaveCount(0);
      expect(
        (await another.request.get("/api/v1/admin/settlements")).status(),
      ).toBe(403);
      await other.goto("/admin/settlements");
      await expect(
        other.getByRole("heading", { name: "Rozliczenia ekipy" }),
      ).toHaveCount(0);
    } finally {
      await Promise.all([player.close(), another.close()]);
    }
  });

  test("reminders use strict amount and age thresholds and exclude pending reports", async ({
    context,
    page,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const player = await playerContext(browser, seed.second, info.project.name);
    try {
      const member = await player.newPage();
      await member.goto("/");
      const homeReminder = member.locator(".settlement-reminder:visible");
      await expect(homeReminder).toContainText(pln(11001));
      await homeReminder
        .getByRole("link", { name: "Przejdź do rozliczeń" })
        .click();
      const reminder = member.getByText("Zaległość wymaga rozliczenia.");
      await expect(reminder).toBeVisible();
      await pay(member, ...seed.charges.slice(5, 7));
      await balances(member, "Moje saldo", [10001, 1000]);
      await expect(reminder).toBeVisible();
      await member.goto("/");
      await expect(homeReminder).toContainText(pln(10001));
      await homeReminder
        .getByRole("link", { name: "Przejdź do rozliczeń" })
        .click();
      await pay(member, seed.charges[4]);
      await balances(member, "Moje saldo", [10000, 1001]);
      await expect(reminder).toHaveCount(0);
      await member.goto("/");
      await expect(homeReminder).toHaveCount(0);
      await member.goto("/settlements");
      await pay(member, seed.charges[3]);
      await balances(member, "Moje saldo", [0, 11001]);
      await page.goto("/admin/settlements");
      const account = card(page, `Bartek Rozliczenia ${info.project.name}`);
      await account.getByText("Historia wpłat", { exact: true }).click();
      const oldReport = account
        .locator(".settlement-list li")
        .filter({ hasText: /10,00.*Czeka na potwierdzenie/ });
      await oldReport
        .getByRole("button", { name: "Odrzuć zgłoszenie" })
        .click();
      await oldReport
        .getByLabel("Powód odrzucenia")
        .fill("Sprawdzenie znacznika wieku");
      await oldReport
        .getByRole("button", { name: "Potwierdź odrzucenie" })
        .click();
      await expect(
        account.getByText("Zapisano decyzję o wpłacie."),
      ).toBeVisible();
      await member.reload();
      await balances(member, "Moje saldo", [1000, 10001]);
      await expect(reminder).toBeVisible();
      await member.goto("/");
      await expect(homeReminder).toContainText(pln(1000));
    } finally {
      await player.close();
    }
  });

  test("a correction after payment preserves history and credits the difference", async ({
    context,
    page,
    browser,
  }, info) => {
    const seed = fixture(info.project.name);
    await adminLogin(context);
    const panel = await showAttendance(page, seed.correction);
    await expect(
      panel
        .getByRole("list", { name: "Podział kosztu" })
        .getByText(pln(5000), { exact: false }),
    ).toHaveCount(4);
    await panel
      .getByRole("button", { name: "Potwierdź sprawdzoną obecność" })
      .click();
    const payer = await playerContext(browser, seed.payer, info.project.name);
    try {
      const member = await payer.newPage();
      await member.goto("/settlements");
      await pay(member, seed.correction);
      await adminReview(
        page,
        `Celina Rozliczenia ${info.project.name}`,
        "paid",
      );
      await page.goto(`/meetings/${seed.correction}`);
      await panel.getByRole("button", { name: /01 Obecność/ }).click();
      await panel.getByText("Osoby z rezerwy i dopisanie na sali").click();
      await panel
        .getByLabel("Dopisz istniejący profil")
        .selectOption(seed.second_id);
      await expect(
        panel.getByRole("list", { name: "Zmiany opłat" }).getByText(/Celina/),
      ).toContainText(/50,00.*40,00/);
      await panel
        .getByRole("button", { name: "Potwierdź i dopisz obecną osobę" })
        .click();
      await expect(
        panel.locator(".attendance-list li").filter({ hasText: "Bartek" }),
      ).toContainText("Obecny/a");
      await member.reload();
      const ledger = await (
        await payer.request.get("/api/v1/me/settlements")
      ).json();
      expect(
        ledger.reports.find((report: { meeting_ids: string[] }) =>
          report.meeting_ids.includes(seed.correction),
        ),
      ).toMatchObject({ amount: 5000, status: "paid" });
      expect(
        ledger.charges.find(
          (charge: { meeting_id: string }) =>
            charge.meeting_id === seed.correction,
        ),
      ).toMatchObject({ amount: 4000, paid: 5000, due: 0 });
      await expect(member.getByText(/Opłacone 50,00/)).toBeVisible();
      await balances(member, "Moje saldo", [0, 0, 1000]);
      await panel.getByText("Korekta kosztu spotkania").click();
      await panel.getByLabel("Koszt spotkania (PLN)").fill("250");
      await panel.getByLabel("Powód korekty kosztu").fill("Dopłata za salę");
      await panel
        .getByRole("button", { name: "Pokaż podgląd korekty kosztu" })
        .click();
      await expect(panel.getByText(/Nowy koszt 250,00/)).toBeVisible();
      await panel
        .getByRole("button", { name: "Zatwierdź korektę kosztu" })
        .click();
      await expect(panel.getByText(/Nowy koszt 250,00/)).toHaveCount(0);
    } finally {
      await payer.close();
    }
  });
});
