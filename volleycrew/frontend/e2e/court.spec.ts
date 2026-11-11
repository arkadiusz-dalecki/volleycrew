import { expect, test } from "@playwright/test";
import { adminLogin } from "./auth-helpers";
import type { components } from "../src/lib/api/schema";

test("court fits team sizes and centers unequal formations around the net", async ({
  page,
  context,
}, info) => {
  const meeting = JSON.parse(process.env.E2E_ROOM_MEETINGS!)[info.project.name];
  await adminLogin(context);
  const attendance = await (
    await context.request.get(`/api/v1/admin/meetings/${meeting.id}/attendance`)
  ).json();
  const players = attendance.players.map(
    (row: components["schemas"]["AttendancePlayer"]) => row.player,
  );
  const csrf = await (await context.request.get("/api/v1/auth/csrf")).json();
  const login = await context.request.post("/api/v1/auth/login", {
    headers: { Origin: "http://127.0.0.1:5175", "X-CSRF-Token": csrf.token },
    data: { profile_id: players[0].id, pin: "123456" },
  });
  expect(login.ok()).toBe(true);
  // This geometry fixture represents published, official teams.
  const detail = await (
    await context.request.get(`/api/v1/meetings/${meeting.id}`)
  ).json();
  await page.route(`**/api/v1/meetings/${meeting.id}`, (route) =>
    route.fulfill({ json: { ...detail, status: "teams_confirmed" } }),
  );
  let sizes = [3, 3];
  await page.route(`**/api/v1/meetings/${meeting.id}/teams`, (route) => {
    const team = (count: number, offset: number) =>
      players
        .slice(offset, offset + count)
        .map(
          (
            player: components["schemas"]["PublicPlayer"],
            position: number,
          ) => ({ player, position, rating: 1000 }),
        );
    const view: components["schemas"]["TeamsView"] = {
      meeting_id: meeting.id,
      version: 1,
      revision: 1,
      state: "confirmed",
      method: "balanced",
      average_a: 1000,
      average_b: 1000,
      team_a: team(sizes[0], 0),
      team_b: team(sizes[1], 7),
    };
    return route.fulfill({ json: view });
  });
  for (sizes of [
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 4],
    [5, 5],
    [6, 6],
    [7, 7],
    [4, 5],
    [5, 4],
    [4, 6],
    [6, 4],
  ]) {
    await page.goto(`/meetings/${meeting.id}?formation=${sizes.join("-")}`);
    const court = page.getByLabel("Składy na boisku", { exact: true });
    for (const side of [0, 1]) {
      const half = court.locator(`.court-half.side-${side}`);
      await expect(half.locator(".court-player")).toHaveCount(
        Math.min(sizes[side], 6),
      );
      const geometry = await half.evaluate((el) => {
        const rect = el.getBoundingClientRect();
        const form = el
          .querySelector(".court-formation")!
          .getBoundingClientRect();
        const cards = [...el.querySelectorAll(".court-player")].map((p) => {
          const box = p.getBoundingClientRect();
          return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
        });
        return {
          center: { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 },
          formation: {
            x: form.x + form.width / 2,
            y: form.y + form.height / 2,
          },
          cards,
        };
      });
      for (const axis of ["x", "y"] as const) {
        expect(
          Math.abs(geometry.center[axis] - geometry.formation[axis]),
        ).toBeLessThan(1);
        if (sizes[side] === 4) {
          const center =
            geometry.cards.reduce((sum, p) => sum + p[axis], 0) / 4;
          expect(Math.abs(center - geometry.center[axis])).toBeLessThan(1);
        }
      }
      if (sizes[side] === 3) {
        const axis = info.project.name === "desktop" ? "x" : "y";
        const front = geometry.cards[0][axis],
          back = geometry.cards[1][axis];
        expect(side === 0 ? front > back : front < back).toBe(true);
      }
    }
    await expect(court.locator(".court-empty")).toHaveCount(0);
    await expect(court.locator(".court-rotation .court-player")).toHaveCount(
      sizes.filter((n) => n === 7).length,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (sizes[0] === 4 && sizes[1] === 5) {
      await court.screenshot({
        path: info.outputPath("court-4-vs-5-centered.png"),
        scale: "css",
      });
    }
  }
});
