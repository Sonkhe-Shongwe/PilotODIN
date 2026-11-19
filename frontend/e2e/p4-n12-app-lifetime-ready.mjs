import { readBrowserProcessId, waitForNativeCloseRegistration } from './p4-n12-native-close-readiness.mjs';
import { discoverUniqueDevPage } from './p4-73-cdp-target-discovery.mjs';

const [scope = 'lifetime', action, ...extra] = process.argv.slice(2);
const consent = new Map([
  ['lifetime', ['PILOTODIN_N12_APP_LIFETIME_CONSENT', 'I_APPROVE_ONE_N12_APP_LIFETIME']],
  ['webview-storage', ['PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT', 'I_APPROVE_ONE_N12_WEBVIEW_STORAGE']],
]).get(scope);
if (!consent || (action !== undefined && action !== '--check-consent') || extra.length) {
  throw Error('Invalid native readiness probe arguments');
}
const required = {
  CI: 'true',
  GITHUB_ACTIONS: 'true',
  RUNNER_OS: 'Windows',
  RUNNER_ENVIRONMENT: 'github-hosted',
  GITHUB_RUN_ATTEMPT: '1',
  [consent[0]]: consent[1],
};
if (Object.entries(required).some(([key, value]) => process.env[key] !== value)) {
  throw Error('Native lifetime readiness requires the approved hosted fixture');
}

async function verifyNativeReadiness() {
  const { chromium } = await import('@playwright/test');
  const { closeN12Peer, findN12Peer } = await import('./p4-n12-native-cases.mjs');
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
    await waitForNativeCloseRegistration(result.page);
    if (scope === 'webview-storage') {
      return { closeReady: true, browserPid: await readBrowserProcessId(browser) };
    }
  } finally {
    await browser.close();
  }
}

if (action === '--check-consent') {
  console.log('N12 native readiness consent preflight passed');
} else {
  const receipt = await verifyNativeReadiness();
  console.log(receipt ? JSON.stringify(receipt) : 'N12 app lifetime native close listener ready and peer closed');
}
