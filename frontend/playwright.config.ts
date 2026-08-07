import { defineConfig } from "@playwright/test";

const externalServers = process.env.PLAYWRIGHT_EXTERNAL_SERVERS === "1";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  fullyParallel: true,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  webServer: externalServers ? undefined : [
    {
      command: "npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "python -m uvicorn backend.api.main:app --port 8000",
      cwd: "..",
      env: { NEULIT_PROFILE: "fake" },
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
