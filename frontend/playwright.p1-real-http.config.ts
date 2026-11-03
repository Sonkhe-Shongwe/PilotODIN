import {defineConfig} from '@playwright/test';

// The dedicated test may never attach to an owner's running dev backend.
// Both servers are owned and stopped by Playwright on a fresh CI runner.
if (process.env.CI !== 'true' || process.env.P1_REAL_HTTP_E2E !== '1'
  || !process.env.PILOTODIN_HOME || !process.env.GITHUB_RUN_ID
  || !process.env.RUNNER_TEMP) {
  throw new Error('P1 real-HTTP acceptance requires the isolated GitHub CI runner.');
}
export default defineConfig({
  testDir:'./e2e',
  testMatch:'p1-real-http.spec.ts',
  timeout:60_000,
  expect:{timeout:10_000},
  fullyParallel:false,
  workers:1,
  retries:0,
  reporter:'list',
  outputDir:'./test-results-p1-real-http',
  use:{
    baseURL:'http://127.0.0.1:5188',
    browserName:'chromium',
    headless:true,
    viewport:{width:1440,height:900},
    serviceWorkers:'block',
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
  },
  webServer:[
    {command:'cd .. && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log',
     url:'http://127.0.0.1:8000/api/health',reuseExistingServer:false,timeout:90_000},
    {command:'npx vite --host 127.0.0.1 --port 5188 --strictPort',
     url:'http://127.0.0.1:5188',reuseExistingServer:false,timeout:60_000},
  ],
});
