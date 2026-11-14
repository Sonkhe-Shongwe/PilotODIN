import { expect } from '@playwright/test';
import { hasTauriNativeBridge } from './p4-73-cdp-target-discovery.mjs';
import { approveQualityChange } from './p4-quality-version-transition.mjs';

const PEER_URL = 'http://127.0.0.1:5173/index.html?n12-peer=1#/studio/overview';

export function isN12Peer(page) {
  return page.url() === PEER_URL;
}

export async function findN12Peer(context) {
  const select = () => context.pages().filter(isN12Peer);
  await expect.poll(() => select().length, { timeout: 15000 }).toBe(1);
  const [peer] = select();
  await expect.poll(() => hasTauriNativeBridge(peer), { timeout: 15000 }).toBe(true);
  return peer;
}

export async function approveCompactQuality(page) {
  const session = await page.context().newCDPSession(page);
  try {
    await session.send('Emulation.setDeviceMetricsOverride', {
      width: 730, height: 540, deviceScaleFactor: 0, mobile: false,
    });
    await approveQualityChange(page, async (dialog, approve) => {
      await approve.scrollIntoViewIfNeeded();
      await expect(approve).toBeInViewport({ ratio: 1 });
      expect(await dialog.evaluate(element => {
        const { left, right, top, bottom } = element.getBoundingClientRect();
        return innerWidth === 730 && left >= 0 && right <= innerWidth && top >= 0 && bottom <= innerHeight;
      })).toBe(true);
    });
    console.log('N12 compact Quality review and exact approval: PASS');
  } finally {
    await session.send('Emulation.clearDeviceMetricsOverride');
    await session.detach();
  }
}

export function matchesN12LifecycleRequest(request, api, permit) {
  if (!permit || request.method() !== 'PUT' ||
      request.url() !== `${api}/projects/${permit.id}/lifecycle`) return false;
  try {
    const body = request.postDataJSON();
    return Object.keys(body).length === 2 && body.action === permit.action &&
      body.expected_revision === permit.revision;
  } catch {
    return false;
  }
}

export async function verifyN12ArchiveDraft(page, peer, api, projectId, read, permitOnce) {
  const primary = page.locator('.po-primary-pane .po-pane-content');
  const target = page.getByLabel('TARGET VARIABLE');
  const chooser = page.getByRole('combobox', { name: 'Switch project' });
  const warning = page.locator('.po-shell-warning');
  const option = chooser.locator(`option[value="${projectId}"]`);
  const projectUrl = `${api}/projects/${projectId}`;
  const historyUrl = `${projectUrl}/quality/history`;
  await expect(chooser).toHaveValue(projectId);
  await expect(target).toHaveValue('churn');
  const pane = await primary.elementHandle();
  try {
    const history = await read(historyUrl);
    expect(history.status).toBe(200);
    const historyBefore = await history.json();
    const currentName = await option.textContent();

    // The native peer applies only the selected fixture's reversible lifecycle action.
    // Use the real lifecycle signal, so the observing Studio re-reads live metadata.
    for (const [revision, action] of ['archive', 'restore'].entries()) {
      permitOnce({ id: projectId, action, revision });
      expect(await peer.evaluate(async ({ projectUrl, action, revision }) => {
        const response = await fetch(`${projectUrl}/lifecycle`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, expected_revision: revision }),
        });
        if (!response.ok) return { status: response.status };
        const row = await response.json();
        const { publishProjectLifecycleSignal } = await import('/src/projectLifecycleSignal.ts');
        publishProjectLifecycleSignal({ id: row.id, revision: row.revision, archived: row.archived_at !== null });
        return { status: response.status, id: row.id, revision: row.revision, archived: row.archived_at !== null };
      }, { projectUrl, action, revision })).toEqual({
        status: 200, id: projectId, revision: revision + 1, archived: action === 'archive',
      });
      if (action === 'archive') {
        expect((await read(projectUrl)).status).toBe(404);
        await expect(warning).toContainText('This project was archived in another window.');
        await expect(option).toContainText('Archived in another window');
      } else {
        expect((await read(projectUrl)).status).toBe(200);
        await expect(warning).toHaveCount(0);
        await expect(option).toHaveText(currentName);
      }
      await expect(chooser).toHaveValue(projectId);
      await expect(target).toHaveValue('churn');
      expect(await primary.evaluate((element, original) => element === original, pane)).toBe(true);
    }
    const restoredHistory = await read(historyUrl);
    expect(restoredHistory.status).toBe(200);
    expect(await restoredHistory.json()).toEqual(historyBefore);
    console.log('N12 native peer archive and restore preserved the unsaved Prepare target: PASS');
  } finally {
    await pane.dispose();
  }
}

export async function closeN12Peer(peer) {
  const closed = peer.waitForEvent('close', { timeout: 15000 });
  const close = peer.evaluate(() => window.__TAURI_INTERNALS__.invoke('plugin:window|close', { label: 'n12peer' }));
  // Closing the WebView can destroy its IPC response. Require the CDP close event.
  await Promise.all([closed, close.catch(() => {})]);
}
