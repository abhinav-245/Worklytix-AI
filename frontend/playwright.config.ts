import { defineConfig, devices } from "@playwright/test";

/**
 * Reusable browser UI verification for FIT-INTEL.
 *
 * Uses Playwright's own Chromium (deterministic; independent of any
 * installed Chrome). `webServer` reuses `http://localhost:3000` when it
 * is already up, otherwise starts `next dev` automatically.
 *
 * Primary command (from frontend/):  npm run test:e2e
 * Failure evidence: test-results/ (screenshots) + traces on failure.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-mobile",
      use: {
        ...devices["Pixel 7"],
        viewport: { width: 375, height: 812 },
      },
    },
  ],
});
