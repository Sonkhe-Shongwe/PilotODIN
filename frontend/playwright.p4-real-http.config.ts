import {defineConfig} from '@playwright/test';

// One CI-only P4-05 browser scenario on disposable Uvicorn/SQLite. The borrowed
// P1 backend helper only permits an exact runner-owned temporary location.
if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
   process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.GITHUB_RUN_ID||
   !process.env.RUNNER_TEMP||!process.env.PILOTODIN_HOME){
 throw Error('P4 real HTTP tests require trusted disposable GitHub CI');
}
export default defineConfig({
 testDir:'./e2e',
 testMatch:'p4-real-http-review-queue.spec.ts',
 timeout:90_000,
 expect:{timeout:12_000},
 fullyParallel:false,workers:1,retries:0,reporter:'list',
 outputDir:'./test-results-p4-review-queue',
 use:{
  baseURL:'http://127.0.0.1:5178',
  browserName:'chromium',headless:true,
  viewport:{width:1440,height:900},serviceWorkers:'block',
  trace:'retain-on-failure',screenshot:'only-on-failure',
 },
 webServer:{
  command:'npx vite --host 127.0.0.1 --port 5178 --strictPort',
  url:'http://127.0.0.1:5178',
  reuseExistingServer:false,timeout:60_000,
 },
});
