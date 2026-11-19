// The injected native bridge can appear before the shell registers its close listener.
export async function waitForNativeCloseRegistration(page) {
  await page.locator('.po-unified-shell[data-native-close-ready="true"]').waitFor({
    state: 'visible',
    timeout: 30_000,
  });
}

export async function readBrowserProcessId(browser, timeoutMs = 1500) {
  let timer;
  try {
    const read = async () => {
      // The caller closes the browser connection immediately after readiness.
      const session = await browser.newBrowserCDPSession();
      const { processInfo } = await session.send('SystemInfo.getProcessInfo');
      const candidates = processInfo.filter(process => process.type === 'browser');
      const pid = candidates[0]?.id;
      return candidates.length === 1 && Number.isSafeInteger(pid) && pid > 0 ? pid : null;
    };
    return await Promise.race([
      read(),
      new Promise(resolve => { timer = setTimeout(resolve, timeoutMs, null); }),
    ]);
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
