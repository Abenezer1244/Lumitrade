import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("E2E-007: Sidebar navigation works — click each main nav item and verify URL changes", async ({
    page,
  }) => {
    await page.goto("/dashboard");

    // Wait for sidebar to load
    await expect(page.locator("aside")).toBeVisible({ timeout: 15_000 });

    const navItems = [
      { label: "Signals", url: "/signals" },
      { label: "Trades", url: "/trades" },
      { label: "Analytics", url: "/analytics" },
      { label: "Settings", url: "/settings" },
      { label: "Dashboard", url: "/dashboard" },
    ];

    for (const item of navItems) {
      const link = page.locator("aside").getByRole("link", {
        name: item.label,
        exact: true,
      });
      await link.click();
      await expect(page).toHaveURL(new RegExp(item.url));
    }
  });

  test("E2E-008: TopBar shows page title, PAPER badge, and UTC clock", async ({
    page,
  }) => {
    await page.goto("/dashboard");

    // Page title in the TopBar header
    const topbar = page.locator("header");
    await expect(topbar.getByText("Dashboard")).toBeVisible({
      timeout: 15_000,
    });

    // PAPER badge
    await expect(topbar.getByText("PAPER")).toBeVisible();

    // UTC clock — look for the "UTC" label text
    await expect(topbar.getByText("UTC")).toBeVisible();
  });

  test("E2E-009: Theme toggle switches between dark and light mode", async ({
    page,
  }) => {
    await page.goto("/dashboard");

    // Default theme is dark — html should have data-theme="dark"
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark", {
      timeout: 10_000,
    });

    // Click the theme toggle button (aria-label "Toggle theme")
    const toggleButton = page.getByRole("button", {
      name: /Toggle theme/i,
    });
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    // After toggle, theme should be light
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

    // Toggle back
    await toggleButton.click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("E2E-020: All main nav routes are accessible without errors", async ({
    page,
  }) => {
    const routes = [
      "/dashboard",
      "/signals",
      "/trades",
      "/analytics",
      "/settings",
      "/journal",
      "/coach",
      "/intelligence",
      "/marketplace",
      "/copy",
      "/backtest",
      "/api-keys",
    ];

    const errors: string[] = [];
    page.on("pageerror", (err) => {
      errors.push(err.message);
    });

    for (const route of routes) {
      const response = await page.goto(route);
      // Page should not return a server error
      expect(
        response?.status(),
        `Route ${route} returned HTTP ${response?.status()}`
      ).toBeLessThan(500);
    }

    // Filter out known non-critical errors (e.g., fetch failures to API routes
    // that return 404 in dev when the backend is not running)
    const criticalErrors = errors.filter(
      (e) =>
        !e.includes("fetch") &&
        !e.includes("Failed to fetch") &&
        !e.includes("NetworkError") &&
        !e.includes("ERR_CONNECTION_REFUSED")
    );

    expect(
      criticalErrors,
      `Critical JS errors found: ${criticalErrors.join("; ")}`
    ).toHaveLength(0);
  });
});
