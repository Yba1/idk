import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./video-capture",
  timeout: 900_000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 1920, height: 1080 },
    video: {
      mode: "on",
      size: { width: 1920, height: 1080 },
    },
  },
  outputDir: "./video-capture/output",
});
