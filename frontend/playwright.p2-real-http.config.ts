import {defineConfig} from '@playwright/test';

// Reuse the existing CI-owned disposable Uvicorn helper and its exact
// PILOTODIN_HOME/port protections. No local or owner-data execution allowed.
if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
   process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.GITHUB_RUN_ID||
   !process.env.RUNNER_TEMP||!process.env.PILOTODIN_HOME){
 throw new Error('P2 real HTTP report acceptance requires the isolated GitHub runner');
}
export default defineConfig({
 testDir:'./e2e',
 testMatch:'p2-real-http-report-comparison.spec.ts',
 timeout:90_000,expect:{timeout:10_000},
 fullyParallel:false,workers:1,retries:0,reporter:'list',
 outputDir:'./test-results-p2-real-http',
 use:{
  baseURL:'http://127.0.0.1:5178',
  browserName:'chromium',headless:true,
  viewport:{width:1440,height:900},serviceWorkers:'block',
  trace:'retain-on-failure',screenshot:'only-on-failure',
 },
 webServer:{
  command:'npx vite --host 127.0.0.1 --port 5178 --strictPort',
  url:'http://127.0.0.1:5178',reuseExistingServer:false,timeout:60_000,
 },
});
