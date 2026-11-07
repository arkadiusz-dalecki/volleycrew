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
  await organizer.goto("/admin/settings");
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
  await expect(organizer.getByText("Wyjątek — termin bez zmian")).toBeVisible();
  await organizer.screenshot({
    path: info.outputPath("schedule-preview.png"),
    fullPage: true,
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
