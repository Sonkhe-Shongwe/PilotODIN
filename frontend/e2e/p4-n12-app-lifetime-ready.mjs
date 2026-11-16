import { chromium } from '@playwright/test';
import { discoverUniqueDevPage } from './p4-73-cdp-target-discovery.mjs';
import { closeN12Peer, findN12Peer } from './p4-n12-native-cases.mjs';

const required = {
  CI: 'true',
  GITHUB_ACTIONS: 'true',
  RUNNER_OS: 'Windows',
  RUNNER_ENVIRONMENT: 'github-hosted',
  GITHUB_RUN_ATTEMPT: '1',
  PILOTODIN_N12_APP_LIFETIME_CONSENT: 'I_APPROVE_ONE_N12_APP_LIFETIME',
};
if (Object.entries(required).some(([key, value]) => process.env[key] !== value)) {
  throw Error('Native lifetime readiness requires the approved hosted fixture');
}

const browser = await chromium.connectOverCDP('http://127.0.0.1:9331', { timeout: 15_000 });
try {
  const result = await discoverUniqueDevPage(
    () => browser.contexts().flatMap(context => context.pages()),
    () => new Promise(resolve => setTimeout(resolve, 400)),
  );
  if (result.status !== 'FOUND') {
    throw Error('Native lifetime readiness blocked: ' + result.status);
  }
  const peer = await findN12Peer(result.page.context());
  await closeN12Peer(peer);
  console.log('N12 app lifetime native bridge ready and peer closed');
} finally {
  await browser.close();
}
