import { test, expect } from "@playwright/test";

test.describe("Trades Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/trades");
  });

  test("E2E-011: Trades page shows filters (pair, outcome, date) and empty state", async ({
    page,
  }) => {
    // Wait for loading to complete
    await expect(
      page.getByText(/No trades yet|No trades match/i).first()
    ).toBeVisible({ timeout: 15_000 });

    // Pair filter
    const pairSelect = page.getByRole("combobox").first();
    await expect(pairSelect).toBeVisible();

    // Outcome filter — second combobox
    const outcomeSelect = page.getByRole("combobox").nth(1);
    await expect(outcomeSelect).toBeVisible();

    // Date filters — look for From and To labels
    await expect(page.getByText("From")).toBeVisible();
    await expect(page.getByText("To")).toBeVisible();

    // Empty state message
    await expect(page.getByText("No trades yet.")).toBeVisible();
  });

  test("E2E-012: Trades export button is disabled when no trades", async ({
    page,
  }) => {
    // Wait for page to load
    await expect(
      page.getByText(/No trades yet|No trades match/i).first()
    ).toBeVisible({ timeout: 15_000 });

    // Export button should exist and be disabled
    const exportButton = page.getByRole("button", {
      name: /Export/i,
    });
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeDisabled();
  });
});
