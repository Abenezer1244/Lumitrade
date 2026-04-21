import { test, expect } from "@playwright/test";

test.describe("Login Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/auth/login");
  });

  test("E2E-017: Login page shows email input and sign in button", async ({
    page,
  }) => {
    // LUMITRADE logo
    await expect(page.getByText("LUMITRADE")).toBeVisible();

    // Subtitle
    await expect(page.getByText("AI-Powered Forex Trading")).toBeVisible();

    // Email label and input
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(
      page.getByPlaceholder("trader@example.com")
    ).toBeVisible();

    // Sign In button
    await expect(
      page.getByRole("button", { name: /Sign In/i })
    ).toBeVisible();
  });

  test("E2E-018: Login sign in button disabled without email", async ({
    page,
  }) => {
    // The sign in button should be disabled when email is empty
    const signInButton = page.getByRole("button", { name: /Sign In/i });
    await expect(signInButton).toBeVisible();
    await expect(signInButton).toBeDisabled();

    // Type an email — button should become enabled
    await page.getByPlaceholder("trader@example.com").fill("test@example.com");
    await expect(signInButton).toBeEnabled();

    // Clear the email — button should be disabled again
    await page.getByPlaceholder("trader@example.com").fill("");
    await expect(signInButton).toBeDisabled();
  });
});
