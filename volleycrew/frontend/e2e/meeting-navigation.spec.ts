import { expect, test, type Locator } from "@playwright/test";
import { adminLogin } from "./auth-helpers";

async function swipe(
  target: Locator,
  from: { clientX: number; clientY: number },
  to: { clientX: number; clientY: number },
) {
  await target.dispatchEvent("touchstart", {
    touches: [{ identifier: 1, ...from }],
  });
  await target.dispatchEvent("touchmove", {
    touches: [{ identifier: 1, ...to }],
  });
  await target.dispatchEvent("touchend", {
    touches: [],
    changedTouches: [{ identifier: 1, ...to }],
  });
}

test("meeting swipes and buttons preserve declarations and recover from errors", async ({
  page,
  context,
}, info) => {
  await adminLogin(context);
  const initial = await (
    await context.request.get("/api/v1/meetings/next")
  ).json();
  const params = new URLSearchParams({
    starts_at: initial.starts_at,
    meeting_id: initial.id,
  });
  const pair = await (
    await context.request.get(`/api/v1/meetings/adjacent?${params}`)
  ).json();
  expect(pair.next).not.toBeNull();
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method()))
      mutations.push(new URL(request.url()).pathname);
  });
  await page.goto("/");
  const surface = page.locator(".meeting-navigation-surface");
  await expect(surface).toHaveAttribute("data-meeting-id", initial.id);
  const next = page.getByRole("button", {
    name: "Następne spotkanie",
    exact: true,
  });
  await expect(next).toBeEnabled();
  const hero = page.locator(".hero-date");
  const left = { identifier: 1, clientX: 290, clientY: 240 };
  const right = { identifier: 2, clientX: 80, clientY: 240 };
  for (const [from, to] of [
    [left, { clientX: 275, clientY: 240 }],
    [left, { clientX: 100, clientY: 480 }],
  ]) {
    await swipe(hero, from, to);
    await expect(page).toHaveURL(/\/$/);
  }
  await swipe(next, left, right);
  await expect(page).toHaveURL(/\/$/);
  await hero.dispatchEvent("touchstart", { touches: [left] });
  await hero.dispatchEvent("touchmove", { touches: [left, right] });
  await hero.dispatchEvent("touchend", {
    touches: [],
    changedTouches: [right],
  });
  await expect(page).toHaveURL(/\/$/);
  await hero.dispatchEvent("touchstart", { touches: [left] });
  await hero.dispatchEvent("touchcancel");
  await hero.dispatchEvent("touchend", {
    touches: [],
    changedTouches: [right],
  });
  await expect(page).toHaveURL(/\/$/);

  if (info.project.name === "mobile") {
    // Exercise native Chromium touch handling, including touch-action/pan arbitration.
    const box = (await hero.boundingBox())!;
    const session = await context.newCDPSession(page);
    const y = box.y + box.height / 2;
    await session.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x: box.x + box.width * 0.85, y }],
    });
    for (const fraction of [0.7, 0.5, 0.3, 0.15]) {
      await session.send("Input.dispatchTouchEvent", {
        type: "touchMove",
        touchPoints: [{ x: box.x + box.width * fraction, y }],
      });
    }
    await session.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    });
    await session.detach();
  } else {
    await swipe(hero, left, right);
  }
  await expect(page).toHaveURL(new RegExp(`/meetings/${pair.next.id}$`));
  await expect(surface).toHaveAttribute("data-meeting-id", pair.next.id);
  await expect(
    page.getByRole("button", { name: "Poprzednie spotkanie", exact: true }),
  ).toBeEnabled();
  await swipe(hero, right, left);
  await expect(page).toHaveURL(new RegExp(`/meetings/${initial.id}$`));
  await expect(surface).toHaveAttribute("data-meeting-id", initial.id);
  await expect(next).toBeEnabled();
  await next.click();
  await expect(page).toHaveURL(new RegExp(`/meetings/${pair.next.id}$`));
  await expect(surface).toHaveAttribute("data-meeting-id", pair.next.id);
  await page.reload();
  await expect(hero).toBeVisible();
  expect(mutations.every((path) => path.endsWith("/meetings/resolve"))).toBe(
    true,
  );
  const unchanged = await (
    await context.request.get(`/api/v1/meetings/${initial.id}`)
  ).json();
  expect(unchanged.participant_count).toBe(initial.participant_count);
  expect(unchanged.waitlist_count).toBe(initial.waitlist_count);

  await page.route("**/api/v1/meetings/adjacent?*", (route) => route.abort());
  await page.reload();
  await expect(
    page.getByText("Nie udało się wczytać sąsiednich spotkań.", {
      exact: false,
    }),
  ).toBeVisible({ timeout: 15000 });
  await expect(hero).toBeVisible();
  await expect(next).toBeDisabled();
  await page.unroute("**/api/v1/meetings/adjacent?*");
  await page.getByRole("button", { name: "Ponów nawigację" }).click();
  await expect(
    page.getByRole("button", { name: "Poprzednie spotkanie", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: info.outputPath("meeting-navigation.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
