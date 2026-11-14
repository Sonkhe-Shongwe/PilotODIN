import { expect } from '@playwright/test';

export async function prepareWorkspaceTabDrag(page) {
  const navigation = page.getByRole('navigation', { name: 'Workspace navigation' });
  for (const view of ['Your data', 'Prepare']) {
    const button = navigation.getByRole('button', { name: view, exact: true });
    await button.click();
    // The route is committed after the exit animation. Clicking the next
    // button before this assertion can target the route still being left.
    await expect(button).toHaveAttribute('aria-current', 'page');
  }
  await expect(page.locator('html')).not.toHaveClass(/\bpo-route-animating\b/);
  await expect(page.getByRole('tab', { name: 'Prepare', exact: true }))
    .toHaveAttribute('aria-selected', 'true');
}

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
