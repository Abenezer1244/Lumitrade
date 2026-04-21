import { test, expect } from "@playwright/test";

test.describe("Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
  });

  test("E2E-015: Settings page shows mode toggle and trading parameters", async ({
    page,
  }) => {
    // Wait for settings to load (loaded state replaces the skeleton)
    await expect(
      page.getByText("Trading Mode")
    ).toBeVisible({ timeout: 15_000 });

    // Mode toggle — PAPER and LIVE buttons
    await expect(
      page.getByRole("button", { name: "PAPER", exact: true })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "LIVE", exact: true })
    ).toBeVisible();

    // Trading Parameters heading
    await expect(page.getByText("Trading Parameters")).toBeVisible();

    // Check for the 4 slider labels
    await expect(page.getByText("Max Risk Per Trade")).toBeVisible();
    await expect(page.getByText("Daily Loss Limit")).toBeVisible();
    await expect(page.getByText("Max Open Positions")).toBeVisible();
    await expect(page.getByText("Min Confidence Threshold")).toBeVisible();

    // Save button
    await expect(
      page.getByRole("button", { name: /Save Changes/i })
    ).toBeVisible();
  });

  test("E2E-016: Settings sliders are interactive (can change values)", async ({
    page,
  }) => {
    // Wait for settings to load
    await expect(
      page.getByText("Trading Parameters")
    ).toBeVisible({ timeout: 15_000 });

    // Get the Max Risk Per Trade slider
    const riskSlider = page.getByRole("slider", {
      name: "Max Risk Per Trade",
    });
    await expect(riskSlider).toBeVisible();

    // Read the initial value
    const initialValue = await riskSlider.inputValue();

    // Move the slider to max value
    await riskSlider.fill("2");

    // Verify the value changed
    const newValue = await riskSlider.inputValue();
    expect(newValue).toBe("2");
    expect(newValue).not.toBe(initialValue);

    // Verify the displayed formatted value updated
    await expect(page.getByText("2.0%").first()).toBeVisible();
  });
});
