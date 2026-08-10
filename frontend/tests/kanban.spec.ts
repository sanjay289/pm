import { expect, test } from "@playwright/test";
import { loginAsTestUser } from "./helpers";

// The board is real, persisted state (Part 7) shared across test runs, so
// these tests create their own data rather than assuming a pristine seed
// (e.g. "card-1 starts in col-backlog").

test.beforeEach(async ({ page }) => {
  await loginAsTestUser(page);
});

test("loads the kanban board", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("renames a column and the rename persists after reload", async ({ page }) => {
  await page.goto("/");
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const titleInput = firstColumn.getByLabel("Column title");
  const newTitle = `Renamed ${Date.now()}`;

  const renameSaved = page.waitForResponse(
    (response) => response.url().includes("/api/columns/") && response.request().method() === "PATCH"
  );
  await titleInput.fill(newTitle);
  await renameSaved;

  await page.reload();
  await expect(
    page.locator('[data-testid^="column-"]').first().getByLabel("Column title")
  ).toHaveValue(newTitle);
});

test("adds a card, drags it to another column, and both persist after reload", async ({ page }) => {
  await page.goto("/");
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const targetColumn = page.getByTestId("column-col-review");
  const cardTitle = `Playwright card ${Date.now()}`;

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(cardTitle);
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");

  // Wait for the server-confirmed card (not just the optimistic one, which
  // gets a temp id and is swapped for a differently-keyed DOM node once the
  // real response lands — grabbing coordinates mid-swap flakes).
  const cardCreated = page.waitForResponse(
    (response) => response.url().includes("/api/cards") && response.request().method() === "POST"
  );
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await cardCreated;

  const card = firstColumn.locator('[data-testid^="card-"]').filter({ hasText: cardTitle });
  await expect(card).toBeVisible();

  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(columnBox.x + columnBox.width / 2, columnBox.y + 120, { steps: 12 });
  await page.mouse.up();

  const movedCard = targetColumn.locator('[data-testid^="card-"]').filter({ hasText: cardTitle });
  await expect(movedCard).toBeVisible();

  await page.reload();
  await expect(
    page.getByTestId("column-col-review").locator('[data-testid^="card-"]').filter({ hasText: cardTitle })
  ).toBeVisible();
});
