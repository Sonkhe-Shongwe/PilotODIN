import {defineConfig} from '@playwright/test';

// Dedicated Vite port: never attach Playwright to the owner's live :5173 UI.
// All API requests use the intercepted fixture origin, never the real backend.
// Vite refuses escaped API requests; no Python backend or model is launched.
const browserOrigin='http://127.0.0.1:5187';

export default defineConfig({
  testDir:'./e2e',
  testMatch:'**/*.spec.ts',
  timeout:30_000,
  expect:{timeout:8_000},
  fullyParallel:false,
  workers:1,
  retries:0,
  reporter:'list',
  outputDir:'./test-results',
  use:{
    baseURL:browserOrigin,
    browserName:'chromium',
    headless:true,
    // A service worker must not bypass the test's HTTP route isolation.
    serviceWorkers:'block',
    viewport:{width:1440,height:900},
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
  },
  webServer:{
    command:'npx vite --mode intercepted-fixture --host 127.0.0.1 --port 5187 --strictPort',
    url:browserOrigin,
    reuseExistingServer:false,
    timeout:30_000,
  },
});
