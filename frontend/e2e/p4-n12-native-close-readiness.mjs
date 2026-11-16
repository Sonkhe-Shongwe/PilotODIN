// The injected native bridge can appear before the shell registers its close listener.
export async function waitForNativeCloseRegistration(page) {
  await page.locator('.po-unified-shell[data-native-close-ready="true"]').waitFor({
    state: 'visible',
    timeout: 30_000,
  });
}
