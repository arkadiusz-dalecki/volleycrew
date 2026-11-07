import AxeBuilder from "@axe-core/playwright";
export async function audit(page: import("@playwright/test").Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    nodes: v.nodes.map((n) => ({
      target: n.target,
      summary: n.failureSummary,
    })),
  }));
}

export async function touchTargets(page: import("@playwright/test").Page) {
  return page
    .locator(
      'button, a.button, nav a, summary, input:not([type="checkbox"]):not([type="radio"]), select, textarea, .profile-option',
    )
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        if (!element.checkVisibility()) return [];
        const r = element.getBoundingClientRect();
        return r.width && r.height && (r.width < 43.9 || r.height < 43.9)
          ? [
              {
                text:
                  element.getAttribute("aria-label") ??
                  element.textContent?.trim().slice(0, 60),
                width: r.width,
                height: r.height,
              },
            ]
          : [];
      }),
    );
}
