import { defineConfig } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: ".", testMatch: "ui-redesign.spec.ts", workers: 1, timeout: 30000,
  outputDir: path.resolve(__dirname, "../../.local/ui-redesign/test-results"),
  use: { baseURL: "http://127.0.0.1:3010", viewport: { width: 1440, height: 900 } },
  webServer: { command: "npm run dev -- --hostname 127.0.0.1 --port 3010",
    url: "http://127.0.0.1:3010", reuseExistingServer: true,
    env: { LIVE_DEMO_ENABLED: "true", APP_ENV: "poc", NEXT_TELEMETRY_DISABLED: "1" } },
});
