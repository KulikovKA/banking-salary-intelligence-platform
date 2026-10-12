import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: ".", testMatch: "backend-browser.spec.ts", workers: 1,
  timeout: 60000, expect: { timeout: 10000 },
  outputDir: path.resolve(__dirname, "../../.local/snap17-browser/results"),
  reporter: [["list"]], use: { baseURL: "http://127.0.0.1:3100", viewport: { width: 1440, height: 900 }, trace: "retain-on-failure" },
  webServer: [
    { command: "uv run python frontend/tests/api_server.py", cwd: path.resolve(__dirname, "../.."),
      url: "http://127.0.0.1:8007/health", reuseExistingServer: false, timeout: 120000,
      env: { APP_ENV: "test", LLM_MODE: "fake", INGESTION_MODE: "offline" } },
    { command: "npm run start -- --hostname 127.0.0.1 --port 3100", url: "http://127.0.0.1:3100", reuseExistingServer: false,
      env: { BACKEND_URL: "http://127.0.0.1:8007", NEXT_TELEMETRY_DISABLED: "1", APP_ENV: "test", CHAT_DEMO_MODE: "false" } },
  ],
});
