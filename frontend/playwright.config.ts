import { defineConfig } from "@playwright/test";

const externalServers = process.env.PLAYWRIGHT_EXTERNAL_SERVERS === "1";

// `python` only resolves to something with the backend deps when a venv is
// activated. Overridable so the suite runs without activating one first:
//   NEULIT_PYTHON=../.venv/bin/python npm run test:e2e
const python = process.env.NEULIT_PYTHON ?? "python";

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
      command: `${python} -m uvicorn backend.api.main:app --port 8000`,
      cwd: "..",
      // Several full queries per spec from one IP trips the production
      // 10/min limit. The limiter's own behaviour is covered by
      // backend/tests/test_api_conditions.py, not by the browser suite.
      env: { NEULIT_PROFILE: "fake", NEULIT_RATE_LIMIT: "off" },
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
