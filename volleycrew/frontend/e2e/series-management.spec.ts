import { test, expect } from "./fixtures";
import { adminLogin } from "./auth-helpers";

async function post(
  context: import("@playwright/test").BrowserContext,
  path: string,
  data: unknown,
) {
  const csrf = await context.request.get("/api/v1/auth/csrf");
  return context.request.post(`/api/v1${path}`, {
    headers: {
      Origin: "http://127.0.0.1:5175",
      "X-CSRF-Token": (await csrf.json()).token,
    },
    data,
  });
}

test("delete a cancelled occurrence, edit its series and delete the future series", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const year =
    new Date().getFullYear() +
    10 +
    ["desktop", "mobile", "webkit"].indexOf(info.project.name);
  const month = `${year}-06`;
  const state = await (
    await context.request.get("/api/v1/admin/schedule")
  ).json();
  const body = {
    expected_version: state.version,
    effective_from: `${month}-01`,
    effective_until: `${year}-07-01`,
    weekday: 1,
    local_time: "18:00",
    duration_minutes: 120,
    venue: "Sala testowa",
  };
  const shown = await post(context, "/admin/schedule/preview", body);
  expect(shown.ok()).toBe(true);
  const saved = await post(context, "/admin/schedule/versions", {
    ...body,
    preview_token: (await shown.json()).preview_token,
  });
  expect(saved.ok()).toBe(true);
  const rule = (await saved.json()).rules.find(
    (r: { effective_from: string }) => r.effective_from === body.effective_from,
  );
  const calendar = await (
    await context.request.get(
      `/api/v1/calendar?from=${month}-01&to=${year}-07-01`,
    )
  ).json();
  const slot = calendar.items[0];
  const resolved = await post(context, "/meetings/resolve", {
    schedule_version_id: rule.id,
    source_date: slot.source_date,
  });
  const meeting = await resolved.json();
  expect(
    (
      await post(context, `/admin/meetings/${meeting.id}/cancel`, {
        expected_version: meeting.version,
      })
    ).ok(),
  ).toBe(true);
  await page.goto(`/calendar?month=${month}`);
  const card = page.locator(".agenda-card").filter({ hasText: "Odwołane" });
  await card
    .getByRole("button", { name: "Usuń spotkanie", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Usuń spotkanie", exact: true })
    .click();
  await expect(card).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".agenda-card")).toHaveCount(
    calendar.items.length - 1,
  );
  const series = page.getByTestId(`series-${rule.id}`);
  await series
    .getByRole("button", { name: "Edytuj serię", exact: true })
    .click();
  const editor = page.locator(".series-manager > .card");
  await editor.getByLabel("Dzień tygodnia").selectOption("2");
  await editor.getByLabel("Godzina rozpoczęcia", { exact: true }).fill("19:00");
  await editor
    .getByRole("button", { name: "Pokaż podgląd harmonogramu" })
    .click();
  const savedEdit = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/rules/${rule.id}/edit`) &&
      response.request().method() === "POST",
  );
  await editor.getByRole("button", { name: "Zatwierdź harmonogram" }).click();
  const result = await savedEdit;
  expect(result.ok()).toBe(true);
  const edited = (await result.json()).rules.find(
    (r: { effective_from: string }) => r.effective_from === body.effective_from,
  );
  const wednesdays = Array.from(
    { length: 30 },
    (_, i) => new Date(Date.UTC(year, 5, i + 1)),
  ).filter((day) => day.getUTCDay() === 3).length;
  await expect(page.locator(".agenda-card")).toHaveCount(wednesdays - 1);
  await expect(page.locator(".agenda-card").first()).toContainText("19:00");
  await page
    .getByTestId(`series-${edited.id}`)
    .getByRole("button", { name: "Usuń serię", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Usuń serię", exact: true })
    .click();
  await expect(page.locator(".agenda-card")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Brak spotkań", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("series-deleted.png"),
    fullPage: true,
  });
});

test("organizer can download and preview a signature sheet before the meeting", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const year =
    new Date().getFullYear() +
    20 +
    ["desktop", "mobile", "webkit"].indexOf(info.project.name);
  const settings = await (
    await context.request.get("/api/v1/admin/schedule")
  ).json();
  const response = await post(context, "/admin/meetings", {
    expected_version: settings.version,
    local_date: `${year}-05-05`,
    local_time: "10:00",
    duration_minutes: 60,
    venue: "I LO w Gdańsku",
  });
  expect(response.ok()).toBe(true);
  const meeting = await response.json();
  await page.goto(`/meetings/${meeting.id}`);
  await page
    .getByRole("button", { name: "Potwierdzam obecność", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Masz miejsce na boisku" }),
  ).toBeVisible();
  const pdf = page.waitForResponse((response) =>
    response.url().includes(`/meetings/${meeting.id}/signature-list`),
  );
  await page
    .getByRole("button", { name: "Lista podpisów", exact: true })
    .click();
  const document = await pdf;
  expect(document.ok()).toBe(true);
  expect(document.headers()["x-list-basis"]).toBe("enrollments");
  await expect(
    page.getByRole("region", { name: "Podgląd listy podpisów", exact: true }),
  ).toHaveAttribute("data-rendered", "true");
  await expect(
    page.getByText(/Źródło: aktualne potwierdzone zapisy/),
  ).toBeVisible();
  await expect(
    page.getByText(/Dane spotkania zmieniły się po wygenerowaniu/),
  ).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz aktualny PDF" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain(
    `lista-podpisow-${year}-05-05.pdf`,
  );
  await expect(
    page.getByRole("button", { name: "Pobierz aktualny PDF" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("region", { name: "Podgląd listy podpisów", exact: true }),
  ).toHaveAttribute("data-rendered", "true");
  await expect(
    page.getByText(/Dane spotkania zmieniły się po wygenerowaniu/),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("early-signatures.png"),
    fullPage: true,
  });
});
