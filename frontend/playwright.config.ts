import {defineConfig} from '@playwright/test';

// Dedicated Vite port: never attach Playwright to the owner's live :5173 UI.
// Browser requests to the backend :8000 are intercepted in each test; this
// web server launches no Python backend, model, installer or data migration.
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
    viewport:{width:1440,height:900},
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
  },
  webServer:{
    command:'npx vite --host 127.0.0.1 --port 5187 --strictPort',
    url:browserOrigin,
    reuseExistingServer:false,
    timeout:30_000,
  },
});
