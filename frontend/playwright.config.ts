import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  reporter: [['list'], ['json', { outputFile: 'playwright-report/results.json' }]],
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8877',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } },
    },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
  webServer: {
    command: '../.venv/bin/python ../scripts/ui_test_server.py',
    url: 'http://127.0.0.1:8877/health/live',
    reuseExistingServer: false,
    timeout: 30000,
  },
})
