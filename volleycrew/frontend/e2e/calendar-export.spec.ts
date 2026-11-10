import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";
import { adminLogin } from "./auth-helpers";
import { shiftMonth } from "../src/features/meetings/dates";
import { audit } from "./ui-helpers";

test("choose a personal calendar, download ICS and keep cancelled meetings excluded", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const next = await (
    await context.request.get("/api/v1/meetings/next")
  ).json();
  await page.goto("/");
  await page.getByRole("button", { name: "Użytkownik", exact: true }).click();
  const trigger = page.getByRole("button", {
    name: "Dodaj do kalendarza",
    exact: true,
  });
  await trigger.click();
  const dialog = page.getByRole("dialog", {
    name: "Do jakiego kalendarza dodać?",
  });
  await expect(dialog).toBeVisible();
  const google = dialog.getByRole("link", {
    name: "Google Calendar",
    exact: true,
  });
  const url = new URL((await google.getAttribute("href"))!);
  expect(url.hostname).toBe("calendar.google.com");
  expect(url.searchParams.get("location")).toBe(next.venue);
  const utc = (value: string) =>
    new Date(value)
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\.\d{3}Z$/, "Z");
  expect(url.searchParams.get("dates")).toBe(
    `${utc(next.starts_at)}/${utc(next.ends_at)}`,
  );
  await expect(google).toHaveAttribute("target", "_blank");
  for (const [name, host] of [
    ["Outlook.com", "outlook.live.com"],
    ["Outlook · Microsoft 365", "outlook.office.com"],
  ]) {
    const link = dialog.getByRole("link", { name, exact: true });
    expect(new URL((await link.getAttribute("href"))!).hostname).toBe(host);
  }
  expect(await audit(page)).toEqual([]);
  const downloaded = page.waitForEvent("download");
  await dialog
    .getByRole("button", { name: "Apple Calendar (.ics)", exact: true })
    .click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toMatch(
    /^volleycrew-\d{4}-\d{2}-\d{2}\.ics$/,
  );
  const text = await readFile((await file.path())!, "utf8");
  expect(text).toContain(`DTSTART:${utc(next.starts_at)}`);
  expect(text).toContain(`DTEND:${utc(next.ends_at)}`);
  expect(text).toContain("BEGIN:VCALENDAR");
  expect(text).not.toContain("ATTENDEE");
  await expect(dialog.getByRole("status")).toContainText("Na iPhonie");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("calendar-choice.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
  await expect(trigger).toBeFocused();
  await page.goto(`/meetings/${process.env.E2E_CANCELLED_ID}`);
  await expect(page.getByText("Odwołane", { exact: true })).toBeVisible();
  await expect(trigger).toHaveCount(0);
});

test("calendar cards keep the individual picker without bulk export", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const month = process.env.E2E_CALENDAR_MONTH!;
  await page.goto(`/calendar?month=${month}`);
  await page.getByRole("button", { name: "Użytkownik", exact: true }).click();
  const data = await (
    await context.request.get(
      `/api/v1/calendar?from=${month}-01&to=${shiftMonth(month, 1)}-01&limit=100`,
    )
  ).json();
  const eligible = data.items.filter(
    (item: { status: string; ends_at: string }) =>
      !["cancelled", "completed"].includes(item.status) &&
      Date.parse(item.ends_at) > Date.now(),
  );
  expect(eligible.length).toBeGreaterThan(1);
  await expect(
    page
      .locator(".agenda-list")
      .getByRole("button", { name: "Dodaj do kalendarza", exact: true }),
  ).toHaveCount(eligible.length);
  await expect(
    page
      .locator(".agenda-card.cancelled")
      .getByRole("button", { name: "Dodaj do kalendarza", exact: true }),
  ).toHaveCount(0);
  await page
    .locator(".agenda-list")
    .getByRole("button", { name: "Dodaj do kalendarza", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("dialog", { name: "Do jakiego kalendarza dodać?" }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Zamknij", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Dodaj wiele spotkań do kalendarza",
      exact: true,
    }),
  ).toHaveCount(0);
  expect(await audit(page)).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("individual-calendar-cards.png"),
    fullPage: true,
  });
});
