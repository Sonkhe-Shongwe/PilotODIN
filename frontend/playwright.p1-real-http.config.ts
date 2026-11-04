import {defineConfig} from '@playwright/test';

// Dedicated test refuses local runs. Playwright owns Vite; the test owns the
// Uvicorn child by its process handle so it can explicitly stop/restart it.
if (process.env.CI !== 'true' || process.env.P1_REAL_HTTP_E2E !== '1'
  || !process.env.PILOTODIN_HOME || !process.env.GITHUB_RUN_ID
  || !process.env.RUNNER_TEMP) {
  throw new Error('P1 real-HTTP acceptance requires the isolated GitHub CI runner.');
}
export default defineConfig({
  testDir:'./e2e',
  testMatch:'p1-real-http.spec.ts',
  timeout:90_000,
  expect:{timeout:10_000},
  fullyParallel:false,
  workers:1,
  retries:0,
  reporter:'list',
  outputDir:'./test-results-p1-real-http',
  use:{
    baseURL:'http://127.0.0.1:5178',
    browserName:'chromium',
    headless:true,
    viewport:{width:1440,height:900},
    serviceWorkers:'block',
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
  },
  webServer:{
    command:'npx vite --host 127.0.0.1 --port 5178 --strictPort',
    url:'http://127.0.0.1:5178',reuseExistingServer:false,timeout:60_000,
  },
});
