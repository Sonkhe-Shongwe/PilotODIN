// Playwright recommends two moves over a target that handles dragover.
// https://playwright.dev/docs/input#dragging-manually
export async function dragWorkspaceTab(page, tab, pane) {
  await tab.hover({ timeout: 10000 });
  await page.mouse.down();
  try {
    await pane.hover({ timeout: 10000 });
    await pane.hover({ timeout: 10000 });
  } finally {
    await page.mouse.up();
  }
}
