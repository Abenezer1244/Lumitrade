import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("E2E-001: Landing page loads with hero content", async ({ page }) => {
    // The hero headline should be visible
    await expect(page.getByText("AI-Powered Forex Trading")).toBeVisible();
    await expect(page.getByText("You Can Trust")).toBeVisible();

    // The LUMITRADE brand should appear in the nav
    await expect(
      page.locator("nav").getByText("LUMITRADE")
    ).toBeVisible();

    // The Open Dashboard CTA should be visible
    await expect(
      page.getByRole("link", { name: /Open Dashboard/i })
    ).toBeVisible();
  });

  test("E2E-002: Landing nav links work (Dashboard, Launch App)", async ({
    page,
  }) => {
    // "Dashboard" text link in the nav
    const dashboardLink = page.locator("nav").getByRole("link", {
      name: "Dashboard",
    });
    await expect(dashboardLink).toBeVisible();
    await expect(dashboardLink).toHaveAttribute("href", "/dashboard");

    // "Launch App" button in the nav
    const launchLink = page.locator("nav").getByRole("link", {
      name: /Launch App/i,
    });
    await expect(launchLink).toBeVisible();
    await expect(launchLink).toHaveAttribute("href", "/dashboard");

    // Click Dashboard link and verify navigation
    await dashboardLink.click();
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("E2E-003: Landing page has all 8 sections", async ({ page }) => {
    // 1. Navigation
    await expect(page.locator("nav")).toBeVisible();

    // 2. Hero — headline
    await expect(page.getByText("AI-Powered Forex Trading")).toBeVisible();

    // 3. Demo section — scroll terminal
    await expect(page.getByText("See the Terminal Come Alive")).toBeVisible();

    // 4. Stats section — stats counters
    await expect(page.getByText("Pairs Monitored")).toBeVisible();

    // 5. Features grid
    await expect(
      page.getByText("Enterprise-Grade from Day One")
    ).toBeVisible();

    // 6. How It Works
    await expect(page.getByText("How It Works")).toBeVisible();

    // 7. CTA
    await expect(page.getByText("Ready to Trade Smarter?")).toBeVisible();

    // 8. Footer
    await expect(
      page.getByText("Lumitrade v1.0")
    ).toBeVisible();
  });
});
