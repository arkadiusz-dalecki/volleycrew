import { expect, test } from "./fixtures";
import { adminLogin } from "./auth-helpers";
import { dateLabel } from "../src/features/meetings/dates";

test("distant signup, reserve, organizer proposal and explicit acceptance on another device", async ({
  page,
  browser,
}, info) => {
  const nickname = `Rezerwa-${info.project.name}`;
  await page.goto(`/join#${process.env.E2E_INVITE}`);
  await page.getByLabel("Imię", { exact: true }).fill("Anna");
  await page.getByLabel("Nazwisko", { exact: true }).fill("Nowak");
  await page.getByLabel("Przydomek (opcjonalnie)").fill(nickname);
  await page.getByLabel("Twój PIN", { exact: true }).fill("654321");
  await page.getByLabel("Powtórz PIN", { exact: true }).fill("654321");
  await page.getByRole("button", { name: "Dołączam do gry" }).click();
  await expect(
    page.getByRole("heading", { name: "Najbliższe spotkanie" }),
  ).toBeVisible();
  const id = JSON.parse(process.env.E2E_ENROLLMENT_MEETINGS!)[
    info.project.name
  ];
  const admin = await browser.newContext({
    viewport: page.viewportSize() ?? undefined,
  });
  await adminLogin(admin);
  const response = await admin.request.get(`/api/v1/meetings/${id}`);
  const meeting = await response.json();
  await page.goto(`/calendar?month=${process.env.E2E_CALENDAR_MONTH}`);
  await page
    .getByRole("button", {
      name: `Otwórz spotkanie: ${dateLabel(meeting.starts_at)}`,
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(new RegExp(`/meetings/${id}$`));
  await page.getByRole("button", { name: "Będę", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Jesteś na rezerwie · miejsce 1" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Jesteś na rezerwie · miejsce 1" }),
  ).toBeVisible();
  for (const width of info.project.name !== "desktop"
    ? [360, 390, 430]
    : [1440]) {
    await page.setViewportSize({
      width,
      height: info.project.name !== "desktop" ? 844 : 1000,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`reserve-${width}.png`),
      fullPage: true,
      scale: "css",
    });
  }
  const organizer = await admin.newPage();
  await organizer.goto(`/meetings/${id}`);
  await organizer
    .getByRole("button", { name: "Rezygnuję", exact: true })
    .click();
  await organizer
    .getByRole("button", { name: "Potwierdzam rezygnację" })
    .click();
  await expect(
    organizer.getByRole("button", { name: "Zaproponuj miejsce" }),
  ).toBeVisible();
  await organizer.getByRole("button", { name: "Zaproponuj miejsce" }).click();
  await expect(
    organizer.getByText(
      "Propozycja jest aktywna. Powiadom tę osobę na Messengerze.",
    ),
  ).toBeVisible();
  await organizer.screenshot({
    path: info.outputPath("organizer-offer.png"),
    fullPage: true,
    scale: "css",
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Mamy dla Ciebie wolne miejsce" }),
  ).toBeVisible();
  const participants = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Uczestnicy", exact: true }),
  });
  await expect(
    participants.getByText("Anna Nowak", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Przyjmuję miejsce" }).click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  await organizer.reload();
  await expect(
    organizer.getByText("14 / 14 uczestników", { exact: true }),
  ).toBeVisible();
  const updated = await admin.request.get(`/api/v1/meetings/${id}`);
  const body = await updated.json();
  expect(body.participant_count).toBe(14);
  expect(body.reserved_count).toBe(0);
  expect(JSON.stringify(body)).not.toContain("priority_status");
  await organizer.goto("/admin/settings");
  const row = organizer.getByRole("listitem").filter({ hasText: nickname });
  await row
    .getByRole("combobox", { name: "Status: Anna Nowak" })
    .selectOption("player");
  await expect(row.getByRole("combobox")).toHaveValue("player");
  await page.goto("/profile");
  await expect(page.getByText("Twój status: Zawodnik")).toBeVisible();
  await admin.close();
});
