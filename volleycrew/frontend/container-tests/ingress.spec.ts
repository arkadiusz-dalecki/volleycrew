import { expect, test } from "@playwright/test";
for (const prefix of [
  "",
  "/api/hassio_ingress/volleycrew-test-token",
  "/api/hassio_ingress/another-token",
]) {
  test(`packaged frontend: ${prefix || "direct"}`, async ({ page }, info) => {
    const pending = new Set<import("@playwright/test").Request>();
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/")) pending.add(request);
    });
    page.on("requestfinished", (request) => pending.delete(request));
    page.on("requestfailed", (request) => pending.delete(request));
    async function settled() {
      await expect.poll(() => pending.size).toBe(0);
    }
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const apiPaths: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/v1/"))
        apiPaths.push(new URL(req.url()).pathname);
    });
    await page.goto(prefix + "/profile");
    await expect(page).toHaveURL(new RegExp(`${prefix}/login$`));
    await page
      .getByText("Arkadiusz T*****y — Container", { exact: true })
      .click();
    await page.getByLabel("PIN", { exact: true }).fill("123456");
    await page.getByRole("button", { name: "Wejdź na boisko" }).click();
    await expect(page).toHaveURL(new RegExp(`${prefix}/profile$`));
    await settled();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Mój profil", exact: true }),
    ).toBeVisible();
    await settled();
    const nav = page.getByRole("navigation", {
      name:
        info.project.name === "webkit" ? "Nawigacja mobilna" : "Menu główne",
      exact: true,
    });
    await nav.getByRole("link", { name: "Kalendarz", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${prefix}/calendar$`));
    await settled();
    await page.reload();
    await expect(page.locator(".calendar-card")).toBeVisible();
    const manifest = page.locator('link[rel="manifest"]');
    expect(
      await manifest.evaluate(
        (el: HTMLLinkElement) => new URL(el.href).pathname,
      ),
    ).toBe(prefix + "/manifest.webmanifest");
    expect(apiPaths.length).toBeGreaterThan(2);
    expect(apiPaths.every((path) => path.startsWith(prefix + "/api/v1/"))).toBe(
      true,
    );
    await settled();
    if (process.env.VOLLEYCREW_CONTAINER_MEETING) {
      await page.goto(
        prefix +
          `/admin/meetings/${process.env.VOLLEYCREW_CONTAINER_MEETING}/signature-list`,
      );
      await expect(
        page.getByRole("region", {
          name: "Podgląd listy podpisów",
          exact: true,
        }),
      ).toHaveAttribute("data-rendered", "true");
    }
    expect(errors).toEqual([]);
    await page.screenshot({
      path: info.outputPath(
        prefix ? "ingress-calendar.png" : "direct-calendar.png",
      ),
      fullPage: true,
    });
  });
}
