import { defineConfig, devices } from '@playwright/test'

const vitePort = process.env.VITE_PORT ?? '5173'
const flaskPort = process.env.FLASK_PORT ?? '5001'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: `http://localhost:${vitePort}`,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `VITE_API_PORT=${flaskPort} npx vite --port ${vitePort} --strictPort`,
    url: `http://localhost:${vitePort}`,
    reuseExistingServer: !process.env.CI,
  },
})
