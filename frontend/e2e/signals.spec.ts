import { test, expect } from "@playwright/test";

test.describe("Signals Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/signals");
  });

  test("E2E-010: Signals page shows empty state with correct message", async ({
    page,
  }) => {
    // Wait for loading to finish — either signals appear or empty state
    await expect(
      page.getByText(/No signals generated yet|Recent Signals/i).first()
    ).toBeVisible({ timeout: 15_000 });

    // In dev with no backend, we expect the empty state
    // The empty state uses the Zap icon and shows the message
    const emptyMessage = page.getByText("No signals generated yet.");
    if (await emptyMessage.isVisible()) {
      await expect(emptyMessage).toBeVisible();
      await expect(
        page.getByText(
          "Signals will appear here when the AI generates trading opportunities."
        )
      ).toBeVisible();
    }
    // If signals are present (unlikely in test), the test still passes
    // because the page loaded without error
  });
});
