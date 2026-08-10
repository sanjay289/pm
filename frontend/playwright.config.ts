import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  // The board is real, shared, persistent state now (Part 7) — run tests
  // one at a time so they don't race each other mutating the same board.
  // Tests also don't assume a pristine seed (each creates its own card
  // rather than relying on e.g. "card-1 starts in col-backlog"), since the
  // db at DATABASE_PATH below persists across separate test runs.
  workers: 1,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run --directory ../backend uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
      env: { DATABASE_PATH: "data/e2e.db" },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
