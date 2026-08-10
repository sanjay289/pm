import { expect, test } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

// Real backend, real OpenRouter call — currently blocked on the same
// OPENROUTER_API_KEY issue flagged in docs/PLAN.md for Parts 8 and 9.

test.beforeEach(async ({ page }) => {
  await loginAsTestUser(page);
});

test("asking the assistant to move a card updates the board without a reload", async ({ page }) => {
  await page.goto("/");
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const cardTitle = `Chat card ${Date.now()}`;

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(cardTitle);
  const cardCreated = page.waitForResponse(
    (response) => response.url().includes("/api/cards") && response.request().method() === "POST"
  );
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await cardCreated;

  await page.getByRole("button", { name: /ask ai/i }).click();
  await page.getByLabel("Chat message").fill(`Move the card titled "${cardTitle}" to the Done column.`);

  const chatReplied = page.waitForResponse(
    (response) => response.url().includes("/api/chat") && response.request().method() === "POST"
  );
  await page.getByRole("button", { name: /send/i }).click();
  await chatReplied;

  const doneColumn = page.getByTestId("column-col-done");
  await expect(doneColumn.locator('[data-testid^="card-"]').filter({ hasText: cardTitle })).toBeVisible();
});
