import { expect, test } from "./fixtures";
import { adminLogin } from "./auth-helpers";

test("single exception, schedule preview, reconfirmation, stale organizer tab and cancellation", async ({
  page,
  browser,
}, info) => {
  const nickname = `Termin-${info.project.name}`;
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await page.getByLabel("Imię", { exact: true }).fill("Julia");
  await page.getByLabel("Nazwisko", { exact: true }).fill("Kowalska");
  await page.getByLabel("Przydomek (opcjonalnie)").fill(nickname);
  await page.getByLabel("Twój PIN", { exact: true }).fill("654321");
  await page.getByLabel("Powtórz PIN", { exact: true }).fill("654321");
  await page.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  const year =
    Number(process.env.E2E_CALENDAR_MONTH!.slice(0, 4)) +
    ({ desktop: 1, mobile: 2, webkit: 3 }[info.project.name] ?? 4);
  const month = `${year}-${process.env.E2E_CALENDAR_MONTH!.slice(5)}`;
  await page.goto(`/calendar?month=${month}`);
  await page
    .getByRole("button", { name: /^Otwórz spotkanie:/ })
    .first()
    .click();
  await page.getByRole("button", { name: "Będę", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  const exceptionId = page.url().split("/").at(-1)!;
  const admin = await browser.newContext({
    viewport: page.viewportSize() ?? undefined,
  });
  await adminLogin(admin);
  const organizer = await admin.newPage();
  const original = await (
    await admin.request.get(`/api/v1/meetings/${exceptionId}`)
  ).json();
  const moved = new Date(original.starts_at);
  moved.setUTCDate(moved.getUTCDate() + 1);
  const movedDay = moved.toISOString().slice(0, 10);
  await organizer.goto(`/meetings/${exceptionId}`);
  await organizer.getByRole("button", { name: "Zmień ten termin" }).click();
  await organizer.getByLabel("Nowa data spotkania").fill(movedDay);
  await organizer.getByLabel("Nowa godzina").fill("19:00");
  await organizer.getByRole("button", { name: "Pokaż zmianę terminu" }).click();
  await organizer
    .getByRole("button", { name: "Zatwierdź nowy termin" })
    .click();
  await expect(
    organizer.getByText(
      "Termin zmieniony. Poinformuj grupę na Messengerze o nowym terminie i potwierdzeniach.",
    ),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Potwierdź udział w nowym terminie" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Potwierdzam nowy termin" }).click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  await page.goto(`/calendar?month=${month}`);
  await page
    .getByRole("button", { name: /^Otwórz spotkanie:/ })
    .nth(1)
    .click();
  await page.getByRole("button", { name: "Będę", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  const regularId = page.url().split("/").at(-1)!;
  const stale = await admin.newPage();
  await stale.goto(`/meetings/${regularId}`);
  await stale.getByRole("button", { name: "Odwołaj spotkanie" }).click();
  await organizer.goto("/calendar");
  await organizer.getByRole("button", { name: "Zaplanuj serię" }).click();
  const monday = new Date(original.source_date + "T12:00:00Z");
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const oldDay = (new Date(original.starts_at).getUTCDay() + 6) % 7;
  await organizer
    .getByLabel("Zmiana od dnia")
    .fill(monday.toISOString().slice(0, 10));
  await organizer
    .getByLabel("Dzień tygodnia")
    .selectOption(String((oldDay + 2) % 7));
  await organizer
    .getByLabel("Godzina rozpoczęcia", { exact: true })
    .fill("18:00");
  await organizer
    .getByRole("button", { name: "Pokaż podgląd harmonogramu" })
    .click();
  await expect(
    organizer.getByRole("region", { name: "Podgląd harmonogramu" }),
  ).toBeVisible();
  await expect(
    organizer.getByText("Wyjątek — termin bez zmian").first(),
  ).toBeVisible();
  await organizer.screenshot({
    path: info.outputPath("schedule-preview.png"),
    fullPage: true,
    scale: "css",
  });
  await organizer
    .getByRole("button", { name: "Zatwierdź harmonogram" })
    .click();
  await expect(
    organizer.getByText(
      "Harmonogram zapisany. Poinformuj grupę na Messengerze o zmianie i nowych potwierdzeniach.",
    ),
  ).toBeVisible();
  const kept = await (
    await admin.request.get(`/api/v1/meetings/${exceptionId}`)
  ).json();
  expect(kept.starts_at.slice(0, 10)).toBe(movedDay);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Potwierdź udział w nowym terminie" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("reconfirmation.png"),
    fullPage: true,
    scale: "css",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Potwierdzam nowy termin" }).click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  await stale.getByRole("button", { name: "Potwierdzam odwołanie" }).click();
  await expect(
    stale.getByText(
      "Dane zmieniły się w innej karcie. Odśwież podgląd przed zatwierdzeniem.",
    ),
  ).toBeVisible();
  await stale.getByRole("button", { name: "Odwołaj spotkanie" }).click();
  await stale.getByRole("button", { name: "Potwierdzam odwołanie" }).click();
  await expect(
    stale.getByText(
      "Spotkanie zostało odwołane. Nie powoduje oznaczeń nieobecności.",
    ),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText(
      "Spotkanie zostało odwołane. Nie powoduje oznaczeń nieobecności.",
    ),
  ).toBeVisible();
  await page.getByRole("link", { name: "Wróć do kalendarza" }).click();
  await expect(
    page.locator(".agenda-list").getByText("Odwołane", { exact: true }),
  ).toBeVisible();
  await admin.close();
});

test("calendar organizer adds a single meeting and a bounded weekly series", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const year =
    Number(process.env.E2E_CALENDAR_MONTH!.slice(0, 4)) +
    10 +
    ({ desktop: 1, mobile: 2, webkit: 3 }[info.project.name] ?? 4);
  const start = new Date(`${year}-02-01T12:00:00Z`);
  start.setUTCDate(start.getUTCDate() + ((8 - start.getUTCDay()) % 7));
  const monday = start.toISOString().slice(0, 10);
  const friday = new Date(start);
  friday.setUTCDate(friday.getUTCDate() + 4);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 13);
  const month = monday.slice(0, 7);
  await page.goto(`/calendar?month=${month}`);
  await page
    .getByRole("button", { name: "Dodaj spotkanie", exact: true })
    .click();
  await page
    .getByLabel("Data spotkania", { exact: true })
    .fill(friday.toISOString().slice(0, 10));
  await page.getByLabel("Godzina spotkania", { exact: true }).fill("17:00");
  await page.getByRole("button", { name: "Pokaż podgląd spotkania" }).click();
  await page
    .getByRole("button", { name: "Zatwierdź dodanie spotkania" })
    .click();
  await expect(page.getByText(/^Dodano spotkanie:/)).toBeVisible();
  await page.getByRole("button", { name: "Zaplanuj serię" }).click();
  await page.getByLabel("Zmiana od dnia").fill(monday);
  await page
    .getByLabel("Do dnia (włącznie, opcjonalnie)")
    .fill(end.toISOString().slice(0, 10));
  await page.getByLabel("Dzień tygodnia").selectOption("1");
  await page.getByLabel("Godzina rozpoczęcia", { exact: true }).fill("17:00");
  await page
    .getByRole("button", { name: "Pokaż podgląd harmonogramu" })
    .click();
  await expect(
    page.getByRole("region", { name: "Podgląd harmonogramu" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zatwierdź harmonogram" }).click();
  await expect(page.getByText(/^Harmonogram zapisany\./)).toBeVisible();
  await page.screenshot({
    path: info.outputPath("calendar-admin.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Zaplanuj serię" }).click();
  await page
    .getByRole("button", { name: /^Otwórz spotkanie:/ })
    .first()
    .click();
  await expect(page.locator("h2.hero-date time")).toBeVisible();
  await page.screenshot({
    path: info.outputPath("meeting-date.png"),
    fullPage: true,
  });
  await page.goto("/admin/settings");
  await expect(
    page.getByRole("heading", { name: "Seria spotkań" }),
  ).toHaveCount(0);
});

test("organizer changes and cancels a generated slot directly on its calendar card", async ({
  page,
  context,
  browser,
}, info) => {
  await adminLogin(context);
  const year =
    Number(process.env.E2E_CALENDAR_MONTH!.slice(0, 4)) +
    20 +
    ({ desktop: 1, mobile: 2, webkit: 3 }[info.project.name] ?? 4);
  const month = `${year}-06`;
  await page.goto(`/calendar?month=${month}`);
  const first = page.locator(".agenda-card").first();
  await expect(
    first.getByRole("button", { name: "Zmień termin", exact: true }),
  ).toBeVisible();
  await expect(
    first.getByRole("button", { name: "Odwołaj", exact: true }),
  ).toBeVisible();
  // Selecting a date keeps the changed meeting visible at its new date.
  const dayText = await first.locator(".agenda-date > span").innerText();
  await page
    .getByRole("button", {
      name: new RegExp(`^${Number(dayText)} .*spotkania:`),
    })
    .click();
  await first
    .getByRole("button", { name: "Zmień termin", exact: true })
    .click();
  const original = await first.getByLabel("Nowa data spotkania").inputValue();
  const moved = new Date(`${original}T12:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() + 1);
  const movedDate = moved.toISOString().slice(0, 10);
  await first.getByLabel("Nowa data spotkania").fill(movedDate);
  await first.getByLabel("Nowa godzina", { exact: true }).fill("19:00");
  await first.getByRole("button", { name: "Pokaż zmianę terminu" }).click();
  await page.getByRole("button", { name: "Zatwierdź nowy termin" }).click();
  await expect(page.getByText(/^Termin zmieniony\./)).toBeVisible();
  await expect(first.locator(".agenda-date > span")).toHaveText(
    movedDate.slice(-2),
  );
  await expect(first.locator(".agenda-copy")).toContainText("19:00");
  await expect(page).toHaveURL(new RegExp(`/calendar\\?month=${month}$`));
  await page.screenshot({
    path: info.outputPath("calendar-card-actions.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await first.getByRole("button", { name: "Odwołaj", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Odwołać spotkanie?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Anuluj zmianę" }).click();
  await expect(first.getByText("Zaplanowane", { exact: true })).toBeVisible();
  await first.getByRole("button", { name: "Odwołaj", exact: true }).click();
  await page.getByRole("button", { name: "Potwierdzam odwołanie" }).click();
  await expect(first.getByText("Odwołane", { exact: true })).toBeVisible();
  await expect(
    first.getByRole("button", { name: "Odwołaj", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".agenda-card.cancelled")).toHaveCount(1);
  const member = await browser.newContext();
  const memberPage = await member.newPage();
  await memberPage.goto(`/join#${process.env.E2E_INVITE}`);
  await memberPage.getByLabel("Imię", { exact: true }).fill("Kalendarz");
  await memberPage.getByLabel("Nazwisko", { exact: true }).fill("Zawodnik");
  await memberPage
    .getByLabel("Przydomek (opcjonalnie)")
    .fill(`Kafelki-${info.project.name}`);
  await memberPage.getByLabel("Twój PIN", { exact: true }).fill("654321");
  await memberPage.getByLabel("Powtórz PIN", { exact: true }).fill("654321");
  await memberPage.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(
    memberPage.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  await memberPage.goto(`/calendar?month=${month}`);
  await expect(memberPage.locator(".agenda-card").first()).toBeVisible();
  await expect(
    memberPage.getByRole("button", { name: "Zmień termin", exact: true }),
  ).toHaveCount(0);
  await expect(
    memberPage.getByRole("button", { name: "Odwołaj", exact: true }),
  ).toHaveCount(0);
  await member.close();
});
