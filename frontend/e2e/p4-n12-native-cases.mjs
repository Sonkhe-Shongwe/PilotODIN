import { expect } from '@playwright/test';
import { hasTauriNativeBridge } from './p4-73-cdp-target-discovery.mjs';
import { approveQualityChange } from './p4-quality-version-transition.mjs';

const PEER_URL = 'http://127.0.0.1:5173/p4_n12_lifecycle_peer.html';

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
    const navigation = page.getByRole('navigation', { name: 'Workspace navigation' });
    const collapse = navigation.getByRole('button', { name: 'Collapse navigation sidebar' });
    const wasExpanded = await collapse.isVisible();
    if (wasExpanded) await collapse.click({ timeout: 10000 });
    try {
      await approveQualityChange(page, async (dialog, approve) => {
        await approve.scrollIntoViewIfNeeded({ timeout: 10000 });
        await expect(approve).toBeInViewport({ ratio: 1 });
        expect(await dialog.evaluate(element => {
          const { left, right, top, bottom } = element.getBoundingClientRect();
          return innerWidth === 730 && left >= 0 && right <= innerWidth && top >= 0 && bottom <= innerHeight;
        })).toBe(true);
      });
      console.log('N12 compact Quality review and exact approval: PASS');
    } finally {
      if (wasExpanded) {
        await page.getByRole('button', { name: 'Expand navigation sidebar' }).click({ timeout: 10000 });
      }
    }
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

export async function verifyN12ArchiveDraft(page, peer, api, projectId, read, permitOnce, options={}) {
  // Only the explicitly migrated hosted browser fixture needs the proxy
  // marker. Keep the existing native QA default untouched.
  const hostedProxy=options.hostedProxy===true;
  if(hostedProxy&&api!=='http://127.0.0.1:5178/api')throw Error('Unexpected hosted lifecycle fixture API');
  const primary = page.locator('.po-primary-pane .po-pane-content');
  const target = page.getByLabel('TARGET VARIABLE');
  const chooser = page.getByRole('combobox', { name: 'Switch project' });
  const warning = page.locator('.po-shell-warning');
  const option = chooser.locator(`option[value="${projectId}"]`);
  const projectUrl = `${api}/projects/${projectId}`;
  const historyUrl = `${projectUrl}/quality/history`;
  await expect(chooser).toHaveValue(projectId);
  await expect(target).toHaveValue('churn');
  const pane = await primary.elementHandle({ timeout: 10000 });
  try {
    const history = await read(historyUrl);
    expect(history.status).toBe(200);
    const historyBefore = await history.json();
    const currentName = await option.textContent();

    // The native peer applies only the selected fixture's reversible lifecycle action.
    // Use the real lifecycle signal, so the observing Studio re-reads live metadata.
    for (const [revision, action] of ['archive', 'restore'].entries()) {
      permitOnce({ id: projectId, action, revision });
      expect(await peer.evaluate(async ({ projectUrl, action, revision, hostedProxy }) => {
        const headers={'Content-Type':'application/json'};
        if(hostedProxy){
          if(location.origin!=='http://127.0.0.1:5178')throw Error('Unexpected hosted lifecycle peer');
          headers['X-PilotODIN-Dev-Request']='1';
        }
        const response = await fetch(`${projectUrl}/lifecycle`, {
          method: 'PUT', headers,
          body: JSON.stringify({ action, expected_revision: revision }),
        });
        if (!response.ok) return { status: response.status };
        const row = await response.json();
        const { publishProjectLifecycleSignal } = await import('/src/projectLifecycleSignal.ts');
        publishProjectLifecycleSignal({ id: row.id, revision: row.revision, archived: row.archived_at !== null });
        return { status: response.status, id: row.id, revision: row.revision, archived: row.archived_at !== null };
      }, { projectUrl, action, revision, hostedProxy })).toEqual({
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

/** N12 only: use the native Quality review, never a direct unreviewed mutation. */
export async function verifyN12ReviewedUndo(page, api, projectId, read, reload) {
  const root = `${api}/projects/${projectId}`;
  const historyUrl = `${root}/quality/history`;
  const previewUrl = version => `${root}/quality/preview?offset=0&limit=10&expected_version=${version}`;
  const checked = async url => {
    const response = await read(url);
    expect(response.status).toBe(200);
    return response.json();
  };
  const original = ' retail ';
  const h1 = await checked(historyUrl);
  expect(h1.current_version).toBe(1);
  expect(h1.versions.map(item => [item.version, item.event])).toEqual([[0,'original'],[1,'apply']]);
  expect(h1.actions).toHaveLength(1);
  const action = h1.actions[0];
  expect(action).toMatchObject({kind:'trim_whitespace',column:'segment',active:true,affected_rows:1});
  const v1 = await checked(previewUrl(1));
  expect(v1.rows[0].original.segment).toBe(original);
  expect(v1.rows[0].working.segment).toBe('retail');

  const navigation = page.getByRole('navigation', {name:'Workspace navigation'});
  const primary = page.locator('.po-primary-pane');
  await navigation.getByRole('button', {name:'Quality',exact:true}).click();
  await expect(primary.getByText('WORKING VERSION 1',{exact:true})).toBeVisible();
  await primary.getByRole('button', {name:'History',exact:true}).click();
  const proposed = page.waitForResponse(response => response.request().method()==='POST' &&
    response.url()===`${root}/quality/proposals`);
  await primary.getByRole('button', {name:'Undo',exact:true}).click();
  const proposal = await proposed;
  expect(proposal.status()).toBe(200);
  expect(proposal.request().postDataJSON()).toEqual({
    operation:'undo',expected_version:1,action_id:action.id,
  });
  const receipt = await proposal.json();
  expect(receipt).toMatchObject({project_id:projectId,expected_version:1,operation:'undo',changed_cells:1});
  expect(receipt.proposal_id).toMatch(/^[0-9a-f]{32,64}$/);
  expect(receipt.proposal_hash).toMatch(/^[0-9a-f]{64}$/);
  const dialog = page.getByRole('dialog',{name:'Review exact dataset change'});
  await expect(dialog).toContainText('Working version: v1');
  await expect(dialog).toContainText('Changed cells: 1');
  const committed = page.waitForResponse(response => response.request().method()==='POST' &&
    response.url()===`${root}/quality/commit`);
  await dialog.getByRole('button',{name:'Approve these changes'}).click();
  const commit = await committed;
  expect(commit.status()).toBe(200);
  expect(commit.request().postDataJSON()).toEqual({
    proposal_id:receipt.proposal_id,proposal_hash:receipt.proposal_hash,
  });
  await expect(primary.getByText('WORKING VERSION 2',{exact:true})).toBeVisible();

  const h2 = await checked(historyUrl);
  expect(h2.current_version).toBe(2);
  expect(h2.versions.map(item => [item.version,item.event])).toEqual([
    [0,'original'],[1,'apply'],[2,'undo'],
  ]);
  expect(h2.actions).toHaveLength(1);
  expect(h2.actions[0]).toMatchObject({id:action.id,active:false});
  const v2 = await checked(previewUrl(2));
  expect(v2.rows[0].original.segment).toBe(original);
  expect(v2.rows[0].working.segment).toBe(original);
  expect((await read(previewUrl(1))).status).toBe(409);

  await navigation.getByRole('button',{name:'Prepare',exact:true}).click();
  const review = page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(review).toContainText('Current approved dataset version: 2.');
  await reload(page);
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(projectId);
  await expect(review).toContainText('Current approved dataset version: 2.');
  await expect(page.getByLabel('TARGET VARIABLE')).toHaveValue('');
  console.log('N12 reviewed Quality Undo publishes v2, retains v1 history and refreshes Prepare: PASS');
}

export async function verifyN12ReopenedUndo(read, api, projectId) {
  const root = `${api}/projects/${projectId}/quality`;
  const history = await read(`${root}/history`);
  expect(history.status).toBe(200);
  const data = await history.json();
  expect(data.current_version).toBe(2);
  expect(data.versions.map(item=>[item.version,item.event])).toEqual([
    [0,'original'],[1,'apply'],[2,'undo'],
  ]);
  expect(data.actions).toHaveLength(1);
  expect(data.actions[0]).toMatchObject({kind:'trim_whitespace',column:'segment',active:false});
  const preview = await read(`${root}/preview?offset=0&limit=10&expected_version=2`);
  expect(preview.status).toBe(200);
  const rows = await preview.json();
  expect(rows.rows[0].original.segment).toBe(' retail ');
  expect(rows.rows[0].working.segment).toBe(' retail ');
  expect((await read(`${root}/preview?offset=0&limit=10&expected_version=1`)).status).toBe(409);
  console.log('N12 new native process reopens persisted v2 and inactive Undo history: PASS');
}
