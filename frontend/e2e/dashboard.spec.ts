import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("E2E-004: Dashboard loads with all panels (Account, Today, System Status)", async ({
    page,
  }) => {
    // Account panel — look for BALANCE label (from AccountPanel)
    await expect(page.getByText("BALANCE")).toBeVisible({ timeout: 15_000 });

    // Today panel — look for TODAY text
    await expect(page.getByText(/TODAY/i).first()).toBeVisible();

    // System Status panel — look for system status related content
    await expect(page.getByText(/System Status|SYSTEM/i).first()).toBeVisible();
  });

  test("E2E-005: Dashboard shows Open Positions and Signal Feed sections", async ({
    page,
  }) => {
    // Open Positions section — look for the heading or empty state
    await expect(
      page.getByText(/Open Positions|No open positions/i).first()
    ).toBeVisible({ timeout: 15_000 });

    // Signal Feed section — look for signals heading or empty state
    await expect(
      page.getByText(/Recent Signals|No signals generated/i).first()
    ).toBeVisible();
  });

  test("E2E-006: Kill Switch button is present and clickable (opens confirmation)", async ({
    page,
  }) => {
    // The Kill Switch button should be visible
    const killButton = page.getByRole("button", { name: /Kill Switch/i });
    await expect(killButton).toBeVisible({ timeout: 15_000 });

    // Click it to open the confirmation dialog
    await killButton.click();

    // After clicking, the confirmation prompt should appear
    await expect(page.getByText("Confirm Emergency Halt")).toBeVisible();
    await expect(
      page.getByPlaceholder("HALT TRADING")
    ).toBeVisible();

    // Cancel button should also be present
    await expect(
      page.getByRole("button", { name: /Cancel/i })
    ).toBeVisible();
  });
});
