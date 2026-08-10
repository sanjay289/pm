import type { Page } from "@playwright/test";

export async function loginAsTestUser(page: Page): Promise<void> {
  const response = await page.request.post("/api/login", {
    data: { username: "user", password: "password" },
  });
  if (!response.ok()) {
    throw new Error(`Failed to log in test user: ${response.status()}`);
  }
}
