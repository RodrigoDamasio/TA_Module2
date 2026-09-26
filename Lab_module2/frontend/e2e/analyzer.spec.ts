import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

// Stable snippet: after its first real analysis in production it is cached (0 calls on reruns).
const SNIPPET = "def divide(total, parts):\n    return total / parts\n\nresult = divide(10, 0)\n";

async function pasteCode(page: Page, code: string) {
  await page.getByLabel("Code").fill(code);
}

async function loadSample(page: Page, id: string) {
  const menu = page.getByRole("combobox", { name: "Try a sample" });
  await expect(menu).toBeVisible();
  await menu.selectOption(id);
  await expect(page.getByTestId("results")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("E1: paste code, analyze, see structured results", async ({ page }) => {
  await pasteCode(page, SNIPPET);
  await page.getByRole("button", { name: "Analyze" }).click();
  const results = page.getByTestId("results");
  await expect(results).toBeVisible({ timeout: 60_000 });
  await expect(results.getByRole("heading", { name: "Summary" })).toBeVisible();
  await expect(results.getByRole("heading", { name: /Issues \(\d+\)/ })).toBeVisible();
  await expect(results.getByText("Complexity")).toBeVisible();
  await expect(page.getByTestId("meta")).toContainText("LLM calls");
});

test("E2: a sample shows its stored result without analyzing", async ({ page }) => {
  let analyzeCalls = 0;
  page.on("request", (r) => r.url().endsWith("/analyze") && analyzeCalls++);
  await loadSample(page, "sql-injection");
  await expect(page.getByLabel("Code")).toHaveValue(/SELECT id, email FROM users/);
  await expect(page.getByTestId("results").locator("li").first()).toContainText("Line 7");
  await expect(page.getByTestId("meta")).toContainText("Cached result");
  expect(analyzeCalls).toBe(0);
});

test("E3: invalid input and backend down give friendly errors", async ({ page }) => {
  await pasteCode(page, "   ");
  await expect(page.getByRole("button", { name: "Analyze" })).toBeDisabled();

  await page.route("**/analyze", (route) => route.abort());
  await pasteCode(page, SNIPPET);
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Can't reach the analyzer");
});

test("E4: quota errors show a Retry-After countdown", async ({ page }) => {
  await page.route("**/analyze", (route) =>
    route.fulfill({
      status: 503,
      headers: {
        "Content-Type": "application/problem+json",
        "Retry-After": "30",
        // Cross-origin: without these the browser hides Retry-After from JavaScript
        // (the real backend sends them — checked in the backend's V6).
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Retry-After",
      },
      body: JSON.stringify({
        type: "https://example/problems/llm-quota-exhausted",
        title: "The analysis limit has been reached.",
        status: 503,
        detail: "The free-tier analysis quota is used up; try again shortly.",
      }),
    }),
  );
  await pasteCode(page, SNIPPET);
  await page.getByRole("button", { name: "Analyze" }).click();
  const alert = page.getByRole("main").getByRole("alert");
  await expect(alert).toContainText("quota is used up");
  await expect(alert).toContainText(/You can try again in (30|29|28) s/);
  await expect(page.getByRole("button", { name: "Analyze" })).toBeDisabled();
});

test.describe("E5: mobile", () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test("no horizontal scroll; controls reachable", async ({ page }) => {
    await loadSample(page, "large-module");
    for (const name of ["Language", "Analysis type", "Code"]) {
      await expect(page.getByLabel(name)).toBeVisible();
    }
    await expect(page.getByRole("button", { name: "Analyze" })).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test("E6: no serious accessibility violations with results shown", async ({ page }) => {
  await loadSample(page, "xss");
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
});
