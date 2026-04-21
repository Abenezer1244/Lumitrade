import { test, expect } from "@playwright/test";

test.describe("Stub Pages", () => {
  test("E2E-019: Stub pages show Coming Soon content (test /journal)", async ({
    page,
  }) => {
    await page.goto("/journal");

    // ComingSoon component renders the feature name as a heading
    await expect(page.getByText("Trade Journal AI")).toBeVisible({
      timeout: 15_000,
    });

    // Phase badge
    await expect(page.getByText(/Phase \d+ Feature/i)).toBeVisible();

    // Description text
    await expect(
      page.getByText(/plain-English summary/i)
    ).toBeVisible();

    // Unlock condition
    await expect(page.getByText(/Unlocks when/i)).toBeVisible();
  });
});
