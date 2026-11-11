import { expect, test } from "./fixtures";
import { adminLogin } from "./auth-helpers";
import { audit } from "./ui-helpers";
import type { BrowserContext } from "@playwright/test";

async function write(
  context: BrowserContext,
  path: string,
  data: unknown,
  method = "post",
) {
  const csrf = await (await context.request.get("/api/v1/auth/csrf")).json();
  return context.request.fetch(`/api/v1${path}`, {
    method,
    headers: {
      Origin: "http://127.0.0.1:5175",
      "X-CSRF-Token": csrf.token,
      "Idempotency-Key": crypto.randomUUID(),
    },
    data,
  });
}
async function playerLogin(context: BrowserContext, id: string) {
  const response = await write(context, "/auth/login", {
    profile_id: id,
    pin: "123456",
  });
  expect(response.ok()).toBe(true);
}

test("preliminary ELO court updates after signup and cancellation and shares admin swaps", async ({
  page,
  context,
  browser,
}, info) => {
  test.setTimeout(60_000);
  await adminLogin(context);
  await page.clock.install();
  const year =
    new Date().getFullYear() +
    30 +
    ["desktop", "mobile", "webkit"].indexOf(info.project.name);
  const state = await (
    await context.request.get("/api/v1/admin/schedule")
  ).json();
  const created = await write(context, "/admin/meetings", {
    expected_version: state.version,
    local_date: `${year}-05-05`,
    local_time: "10:00",
    duration_minutes: 60,
    venue: "Sala testowa",
  });
  expect(created.ok()).toBe(true);
  const meeting = await created.json();
  const players: string[] = JSON.parse(process.env.E2E_ROOM_MEETINGS!)[
    info.project.name
  ].players;
  const participants: BrowserContext[] = [];
  for (const id of players.slice(0, 5)) {
    const player = await browser.newContext({
      viewport: page.viewportSize() ?? undefined,
    });
    participants.push(player);
    await playerLogin(player, id);
    if (participants.length <= 4)
      expect(
        (
          await write(
            player,
            `/meetings/${meeting.id}/my-declaration`,
            { term_version: meeting.term_version, declaration: "going" },
            "put",
          )
        ).ok(),
      ).toBe(true);
  }
  await page.goto(`/meetings/${meeting.id}`);
  const preview = page.getByRole("region", {
    name: "Wstępne drużyny",
    exact: true,
  });
  await expect(preview.locator(".court-player")).toHaveCount(4);
  await expect(preview.getByText(/Wyrównane według ELO/)).toBeVisible();
  await preview.locator(".court-half.side-0 .court-player").first().click();
  await preview.locator(".court-half.side-1 .court-player").first().click();
  await expect(
    preview.getByText(/Ręczny podział administratora/),
  ).toBeVisible();
  await expect(
    preview.getByRole("button", { name: "Losuj wstępne składy" }),
  ).toBeEnabled();
  const userPage = await participants[4].newPage();
  await userPage.goto(`/meetings/${meeting.id}`);
  const publicPreview = userPage.getByRole("region", {
    name: "Wstępne drużyny",
    exact: true,
  });
  await expect(
    publicPreview.getByText(/Ręczny podział administratora/),
  ).toBeVisible();
  await expect(publicPreview.locator("button.court-player")).toHaveCount(0);
  await userPage
    .getByRole("button", { name: "Potwierdzam obecność", exact: true })
    .click();
  await expect(publicPreview.locator(".court-player")).toHaveCount(5);
  await expect(publicPreview.getByText(/Wyrównane według ELO/)).toBeVisible();
  await page.clock.fastForward(31_000);
  await expect(preview.locator(".court-player")).toHaveCount(5);
  await userPage
    .getByRole("button", { name: "Rezygnuję", exact: true })
    .click();
  await userPage
    .getByRole("dialog")
    .getByRole("button", { name: "Potwierdzam rezygnację", exact: true })
    .click();
  await expect(publicPreview.locator(".court-player")).toHaveCount(4);
  await expect(publicPreview.getByText(/Wyrównane według ELO/)).toBeVisible();
  await page.clock.fastForward(31_000);
  await expect(preview.locator(".court-player")).toHaveCount(4);
  expect(await audit(userPage)).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const attendance = await (
    await context.request.get(`/api/v1/admin/meetings/${meeting.id}/attendance`)
  ).json();
  expect(attendance.confirmed_at).toBeNull();
  await page.screenshot({
    path: info.outputPath("preliminary-admin.png"),
    fullPage: true,
  });
  await userPage.screenshot({
    path: info.outputPath("preliminary-player.png"),
    fullPage: true,
  });
  for (const player of participants) await player.close();
});
