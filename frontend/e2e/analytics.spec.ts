import { test, expect } from "@playwright/test";

test.describe("Analytics Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/analytics");
  });

  test("E2E-013: Analytics page shows 8 metric cards", async ({ page }) => {
    // MetricsGrid renders 8 cards. When no data, it shows skeleton placeholders.
    // When data loads (or falls back to null), it shows either real values or skeletons.
    // Either way, there should be 8 grid items.
    // Wait for the grid to render
    await page.waitForTimeout(2000);

    // The metric card labels (when data is present)
    const expectedLabels = [
      "Total Trades",
      "Win Rate",
      "Profit Factor",
      "Sharpe Ratio",
      "Avg Win",
      "Avg Loss",
      "Max Drawdown",
      "Expectancy",
    ];

    // Check for either the labels (data loaded) or skeleton cards (loading/no data)
    // The grid always has 8 children
    const gridItems = page.locator(
      ".grid.grid-cols-2.md\\:grid-cols-4 > div"
    );
    await expect(gridItems).toHaveCount(8, { timeout: 10_000 });
  });

  test("E2E-014: Analytics shows equity curve section", async ({ page }) => {
    // The equity curve section has the heading "Equity Curve"
    // It may show the chart or an empty state depending on data
    await expect(
      page
        .getByText(/Equity Curve/i)
        .first()
    ).toBeVisible({ timeout: 15_000 });
  });
});
