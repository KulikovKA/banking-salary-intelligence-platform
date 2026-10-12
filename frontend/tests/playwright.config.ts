import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.tsx?$/,
  testIgnore: "backend-browser.spec.ts",
  outputDir: path.resolve(
    __dirname,
    "../../.local/frontend-chat-mvp/test-results",
  ),
  fullyParallel: true,
  workers: 2,
  timeout: 30000,
  expect: { timeout: 8000 },
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: path.resolve(
          __dirname,
          "../../.local/frontend-chat-mvp/playwright-report",
        ),
        open: "never",
      },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    env: { NEXT_TELEMETRY_DISABLED: "1", CHAT_DEMO_MODE: "true", APP_ENV: "test" },
  },
});
