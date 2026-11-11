import { audit, touchTargets } from "./ui-helpers";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { adminLogin } from "./auth-helpers";

function pdfText(path: string) {
  return execFileSync(
    existsSync("../../.tools/bin/uv") ? "../../.tools/bin/uv" : "uv",
    [
      "run",
      "--project",
      "../backend",
      "--frozen",
      "python",
      "-c",
      "from pypdf import PdfReader; import sys; print(' '.join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))",
      path,
    ],
    { encoding: "utf8" },
  ).replace(/\s+/g, " ");
}

test("attendance, court swap, signature PDF and private correction", async ({
  page,
  browser,
}, info) => {
  test.setTimeout(60_000);
  await page.clock.install();
  const renderErrors: string[] = [];
  page.on("pageerror", (error) => renderErrors.push(error.message));
  page.on("console", (entry) => {
    if (entry.type() === "error" && entry.text().includes("same key"))
      renderErrors.push(entry.text());
  });
  const seed = JSON.parse(process.env.E2E_ROOM_MEETINGS!)[info.project.name];
  await adminLogin(page.context());
  await page.goto(`/meetings/${seed.id}`);
  const panel = page.getByRole("region", {
    name: "Panel organizatora",
    exact: true,
  });
  await expect(
    panel.getByRole("button", { name: "Lista podpisów", exact: true }),
  ).toBeEnabled();
  await panel
    .getByRole("button", { name: "Wszyscy obecni", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Zapisz szkic obecności", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Zatwierdź obecność", exact: true }),
  ).toBeEnabled();
  await panel
    .getByRole("button", { name: "Zatwierdź obecność", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Potwierdź sprawdzoną obecność", exact: true })
    .click();
  const generationUrl = `**/api/v1/admin/meetings/${seed.id}/teams/generate`;
  // Commit on the server, then lose its response: retry must recover the same draft.
  await page.route(generationUrl, async (route) => {
    await route.fetch();
    await route.abort();
  });
  await panel
    .getByRole("button", { name: "Wyrównaj według rankingu", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Ponów tę operację", exact: true }),
  ).toBeVisible();
  const beforeRetry = await (
    await page.request.get(`/api/v1/admin/meetings/${seed.id}/teams`)
  ).json();
  await page.unroute(generationUrl);
  await panel
    .getByRole("button", { name: "Ponów tę operację", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Ponów tę operację", exact: true }),
  ).toHaveCount(0);
  const afterRetry = await (
    await page.request.get(`/api/v1/admin/meetings/${seed.id}/teams`)
  ).json();
  expect(afterRetry.revision).toBe(beforeRetry.revision);
  const court = panel.getByLabel("Składy na boisku", { exact: true });
  await expect(court.getByRole("button", { name: /Zamień:/ })).toHaveCount(14);
  const teamA = court.locator(".court-rotation .side-0 button");
  const teamB = court.locator(".court-rotation .side-1 button");
  const oldA = await teamA.textContent(),
    oldB = await teamB.textContent();
  await teamA.click();
  await teamB.click();
  await expect(teamA).toHaveText(oldB!);
  await expect(teamB).toHaveText(oldA!);
  await panel
    .getByRole("button", { name: "Zapisz poprawki składów", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Zapisz poprawki składów", exact: true }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    page
      .getByLabel("Składy na boisku", { exact: true })
      .getByRole("button", { name: /Zamień:/ }),
  ).toHaveCount(14);
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
    expect(await touchTargets(page)).toEqual([]);
    await court.screenshot({
      path: info.outputPath(`court-detail-${width}.png`),
    });
    await page.screenshot({
      path: info.outputPath(`court-${width}.png`),
      fullPage: true,
      scale: "css",
    });
  }
  expect(await audit(page)).toEqual([]);
  await panel
    .getByRole("button", { name: "Zatwierdź składy", exact: true })
    .click();
  await expect(
    panel.getByText("Składy zatwierdzone — widoczne dla ekipy", {
      exact: true,
    }),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Lista podpisów", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Lista podpisów", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Podgląd listy podpisów", exact: true }),
  ).toHaveAttribute("data-rendered", "true");
  expect(await audit(page)).toEqual([]);
  const signaturePage = await page.context().newPage();
  await signaturePage.goto(page.url());
  await expect(
    signaturePage.getByRole("region", {
      name: "Podgląd listy podpisów",
      exact: true,
    }),
  ).toHaveAttribute("data-rendered", "true");
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Pobierz aktualny PDF", exact: true })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(
    /^lista-podpisow-\d{4}-\d{2}-\d{2}\.pdf$/,
  );
  const downloadPath = info.outputPath("signature-before.pdf");
  await download.saveAs(downloadPath);
  const originalText = pdfText(downloadPath);
  expect(originalText).toContain("Michał Nowak");
  expect(originalText).toContain("Liczba uczestników: 14");
  expect(originalText).not.toContain("Sala desktop");
  expect(originalText).not.toContain("Sala mobile");
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
    await expect(
      page.getByRole("region", { name: "Podgląd listy podpisów", exact: true }),
    ).toHaveAttribute("data-rendered", "true");
    await expect(
      page
        .getByRole("region", { name: "Podgląd listy podpisów", exact: true })
        .locator("canvas"),
    ).toHaveCount(1);
    await page.screenshot({
      path: info.outputPath(`signature-preview-${width}.png`),
      fullPage: true,
      scale: "css",
    });
  }
  await page
    .getByRole("link", { name: "Wróć do spotkania", exact: true })
    .click();
  const player = await browser.newContext({
    viewport: page.viewportSize() ?? undefined,
  });
  const csrf = await (await player.request.get("/api/v1/auth/csrf")).json();
  expect(
    (
      await player.request.post("/api/v1/auth/login", {
        headers: {
          Origin: "http://127.0.0.1:5175",
          "X-CSRF-Token": csrf.token,
        },
        data: { profile_id: seed.players[0], pin: "123456" },
      })
    ).ok(),
  ).toBe(true);
  const playerPage = await player.newPage();
  await playerPage.goto(`/meetings/${seed.id}`);
  await expect(
    playerPage.getByRole("heading", {
      name: "Zatwierdzone drużyny",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    playerPage.getByRole("region", { name: "Panel organizatora", exact: true }),
  ).toHaveCount(0);
  expect(
    (
      await player.request.get(
        `/api/v1/admin/players/${seed.players[1]}/attendance-history`,
      )
    ).status(),
  ).toBe(403);
  expect(
    (
      await player.request.get(
        `/api/v1/admin/meetings/${seed.id}/signature-list?download=true`,
      )
    ).status(),
  ).toBe(403);
  await panel
    .getByLabel("Powód otwarcia składów do poprawy")
    .fill("Pomyłka przy sprawdzaniu obecności");
  await panel
    .getByRole("button", { name: "Otwórz składy do poprawy", exact: true })
    .click();
  await panel.getByRole("button", { name: /01 Obecność/ }).click();
  const row = panel
    .locator(".attendance-list > li")
    .filter({ hasText: "Michał Nowak" });
  await row.getByRole("button", { name: "Korekta", exact: true }).click();
  await panel.getByLabel("Poprawny stan").selectOption("no_show");
  await panel
    .getByLabel("Powód korekty", { exact: true })
    .fill("Omyłkowo zaznaczony na sali");
  await panel
    .getByRole("button", { name: "Zapisz korektę", exact: true })
    .click();
  await expect(row.getByText("Nieobecny/a", { exact: true })).toBeVisible();
  // The old preview remains open on another device/tab. Download must still be fresh.
  const freshPromise = signaturePage.waitForEvent("download");
  await signaturePage
    .getByRole("button", { name: "Pobierz aktualny PDF", exact: true })
    .click();
  const freshDownload = await freshPromise;
  const correctedPath = info.outputPath("signature-after.pdf");
  await freshDownload.saveAs(correctedPath);
  const correctedText = pdfText(correctedPath);
  expect(correctedText).not.toContain("Michał Nowak");
  expect(correctedText).toContain("Liczba uczestników: 13");
  expect(correctedText).not.toContain("Omyłkowo");
  await signaturePage.route(
    `**/api/v1/admin/meetings/${seed.id}/signature-list*`,
    (route) => route.abort(),
  );
  await signaturePage
    .getByRole("button", { name: "Odśwież podgląd", exact: true })
    .click();
  await expect(signaturePage.getByRole("alert")).toContainText(
    "Odśwież podgląd",
  );
  await signaturePage.unroute(
    `**/api/v1/admin/meetings/${seed.id}/signature-list*`,
  );
  await signaturePage
    .getByRole("button", { name: "Odśwież podgląd", exact: true })
    .click();
  await expect(
    signaturePage.getByRole("region", {
      name: "Podgląd listy podpisów",
      exact: true,
    }),
  ).toHaveAttribute("data-rendered", "true");
  await signaturePage.close();
  await playerPage.goto("/profile");
  await expect(
    playerPage.getByRole("heading", {
      name: "Prywatna historia obecności",
      exact: true,
    }),
  ).toBeVisible();
  await expect(playerPage.locator(".history-kind")).toHaveText(
    "Nieobecność bez odwołania",
  );
  await expect(
    playerPage.getByText("Omyłkowo zaznaczony na sali", { exact: true }),
  ).toBeVisible();
  await playerPage.goto(`/admin/players/${seed.players[1]}/history`);
  await expect(
    playerPage.getByText("Omyłkowo zaznaczony na sali", { exact: true }),
  ).toHaveCount(0);
  // Finish the full room workflow: result, retry, public ELO and historical correction.
  await page.bringToFront();
  await panel.getByRole("button", { name: /02 Drużyny/ }).click();
  await panel
    .getByRole("button", { name: "Wyrównaj według rankingu", exact: true })
    .click();
  await expect(
    panel
      .getByLabel("Składy na boisku", { exact: true })
      .getByRole("button", { name: /Zamień:/ }),
  ).toHaveCount(13);
  await panel
    .getByRole("button", { name: "Zatwierdź składy", exact: true })
    .click();
  await panel.getByRole("button", { name: /03 Wynik/ }).click();
  await panel.getByLabel("Sety drużyny A", { exact: true }).fill("5");
  await panel.getByLabel("Sety drużyny B", { exact: true }).fill("3");
  await page.route(`**/api/v1/admin/meetings/${seed.id}/result`, (route) =>
    route.request().method() === "GET" ? route.abort() : route.continue(),
  );
  await page.clock.fastForward(31_000);
  await page.clock.fastForward(2_000);
  await expect(
    panel.getByText("Nie udało się odświeżyć wyniku.", { exact: false }),
  ).toBeVisible();
  await expect(panel.getByLabel("Sety drużyny A", { exact: true })).toHaveValue(
    "5",
  );
  await expect(panel.getByLabel("Sety drużyny B", { exact: true })).toHaveValue(
    "3",
  );
  await page.unroute(`**/api/v1/admin/meetings/${seed.id}/result`);
  await page.clock.fastForward(31_000);
  await expect(
    panel.getByText("Nie udało się odświeżyć wyniku.", { exact: false }),
  ).toHaveCount(0);
  await panel
    .getByRole("button", { name: "Pokaż podgląd punktów", exact: true })
    .click();
  await panel
    .locator(".result-editor")
    .screenshot({ path: info.outputPath("result-preview.png") });
  expect(await audit(page)).toEqual([]);
  const resultUrl = `**/api/v1/admin/meetings/${seed.id}/result`;
  await page.route(resultUrl, async (route) => {
    if (route.request().method() === "POST") {
      await route.fetch();
      await route.abort();
    } else await route.continue();
  });
  await panel
    .getByRole("button", { name: "Zapisz wynik i ranking", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "Ponów tę operację", exact: true }),
  ).toBeVisible();
  await page.unroute(resultUrl);
  await panel
    .getByRole("button", { name: "Ponów tę operację", exact: true })
    .click();
  await expect(
    panel.getByRole("button", {
      name: "Skoryguj wynik lub składy",
      exact: true,
    }),
  ).toBeVisible();
  await page.reload();
  await expect(panel.getByLabel("Wynik 5 do 3", { exact: true })).toBeVisible();
  const posted = await (
    await page.request.get(`/api/v1/meetings/${seed.id}/result`)
  ).json();
  expect(posted.revision).toBe(1);
  expect(posted.players).toHaveLength(13);
  expect(
    posted.players.some(
      (p: { player: { id: string } }) => p.player.id === seed.players[0],
    ),
  ).toBe(false);
  await playerPage.goto(`/meetings/${seed.id}`);
  await expect(
    playerPage.getByRole("heading", { name: "Wynik spotkania", exact: true }),
  ).toBeVisible();
  await playerPage.goto("/ranking");
  await expect(
    playerPage.getByRole("heading", { name: "Ranking ekipy", exact: true }),
  ).toBeVisible();
  for (const width of info.project.name !== "desktop"
    ? [360, 390, 430]
    : [1440]) {
    await playerPage.setViewportSize({
      width,
      height: info.project.name !== "desktop" ? 844 : 1000,
    });
    expect(
      await playerPage.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await playerPage.screenshot({
      path: info.outputPath(`ranking-${width}.png`),
      fullPage: true,
      scale: "css",
    });
  }
  await playerPage
    .getByRole("button", { name: "Historia spotkań", exact: true })
    .click();
  await expect(
    playerPage.locator(".result-history-score").first(),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Skoryguj wynik lub składy", exact: true })
    .click();
  await panel
    .getByLabel("Powód korekty wyniku lub składu", { exact: true })
    .fill("Poprawka historycznego składu");
  await panel
    .locator("summary")
    .filter({ hasText: "Popraw historyczny skład i obecność" })
    .click();
  await panel
    .getByRole("combobox", {
      name: "Dodaj faktycznego uczestnika",
      exact: true,
    })
    .selectOption(seed.players[0]);
  await panel
    .getByRole("combobox", { name: "Do drużyny", exact: true })
    .selectOption("A");
  await panel
    .getByRole("button", { name: "Dodaj do składu", exact: true })
    .click();
  await panel
    .getByLabel("Prywatny powód korekty obecności", { exact: true })
    .fill("Dotarł na salę, pominięty we wpisie");
  await panel
    .getByRole("button", { name: "Pokaż podgląd punktów", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Zatwierdź korektę", exact: true })
    .click();
  await expect(
    panel.getByRole("button", {
      name: "Skoryguj wynik lub składy",
      exact: true,
    }),
  ).toBeVisible();
  const fixed = await (
    await page.request.get(`/api/v1/meetings/${seed.id}/result`)
  ).json();
  expect(fixed.revision).toBe(2);
  expect(fixed.players).toHaveLength(14);
  expect(JSON.stringify(fixed)).not.toContain("Dotarł na salę");
  await playerPage.goto(`/ranking/players/${seed.players[0]}`);
  await expect(
    playerPage.getByRole("heading", { name: "Historia punktów", exact: true }),
  ).toBeVisible();
  await expect(playerPage.locator(".rating-history-list li")).toHaveCount(1);
  await playerPage.goto("/profile");
  await expect(playerPage.locator(".history-kind")).toHaveText("Obecność");
  await expect(
    playerPage.getByText("Dotarł na salę, pominięty we wpisie", {
      exact: true,
    }),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Skoryguj wynik lub składy", exact: true })
    .click();
  await panel.getByLabel("Sety drużyny A", { exact: true }).fill("0");
  await panel.getByLabel("Sety drużyny B", { exact: true }).fill("0");
  await panel
    .getByLabel("Powód korekty wyniku lub składu", { exact: true })
    .fill("Zamknięcie bez rozegranych setów");
  await panel
    .getByRole("button", { name: "Pokaż podgląd punktów", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Zatwierdź korektę", exact: true })
    .click();
  await expect(panel.getByLabel("Wynik 0 do 0", { exact: true })).toBeVisible();
  await playerPage.goto(`/ranking/players/${seed.players[0]}`);
  await expect(
    playerPage.getByText(
      "Nie ma jeszcze meczów zmieniających punkty tego zawodnika.",
      { exact: true },
    ),
  ).toBeVisible();
  const finalResult = await (
    await page.request.get(`/api/v1/meetings/${seed.id}/result`)
  ).json();
  expect(finalResult.state).toBe("no_sets");
  expect(finalResult.revisions).toHaveLength(3);
  await player.close();
  expect(renderErrors).toEqual([]);
});
