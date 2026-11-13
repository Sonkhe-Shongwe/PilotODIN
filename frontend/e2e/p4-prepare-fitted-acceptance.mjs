import { expect } from '@playwright/test';
import { openP4FixtureWorkspace } from './p4-open-fixture-workspace.mjs';

const fixture = [
  'TransactionID,churn,event_type,amount',
  ...Array.from({ length: 40 }, (_, i) => [
    `SYNTH-${String(i).padStart(3, '0')}`, i % 2 ? 'Y' : 'N',
    i === 1 ? '" retail "' : i % 5 === 0 ? '' : i % 3 ? 'service' : 'retail',
    i % 7 === 0 ? '' : 100 + i,
  ].join(',')),
].join('\n') + '\n';

async function readJson(response, status, step) {
  expect(response.status, step).toBe(status);
  return response.json();
}

export async function verifyPrepareFittedAcceptance(page, { site, api, request, allowRead = () => {}, requireEmptyStore = true }) {
  const get = (path, status, step) => request(api + path).then(response => readJson(response, status, step));
  const post = (path, body, status, step) => request(api + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(response => readJson(response, status, step));

  if (requireEmptyStore) expect(await get('/projects', 200, 'empty disposable catalogue')).toEqual([]);
  const form = new FormData();
  form.append('file', new Blob([fixture], { type: 'text/csv' }), 'p4-r05-synthetic.csv');
  const created = await request(api + '/projects', { method: 'POST', body: form });
  const { id: projectId } = await readJson(created, 201, 'upload generated fixture');
  expect(projectId).toMatch(/^[0-9a-f]{32}$/);
  const project = `/projects/${projectId}`;
  allowRead(project);

  async function applyQuality(proposal, expectedVersion) {
    const { proposal_id, proposal_hash } = await post(project + '/quality/proposals', proposal, 200, 'preview synthetic Quality change');
    const applied = await post(project + '/quality/commit', { proposal_id, proposal_hash }, 200, 'apply synthetic Quality change');
    expect(applied).toMatchObject({ approved: true, version: expectedVersion });
  }

  await applyQuality({ operation: 'autopilot', expected_version: 0 }, 1);
  await openP4FixtureWorkspace(page, site, projectId);
  await expect(page.getByRole('combobox', { name: 'Switch project' })).toHaveValue(projectId);
  await page.getByLabel('TARGET VARIABLE').selectOption('churn');
  const audit = page.locator('.po-ml-feature-audit tbody');
  const row = name => audit.getByRole('row').filter({ hasText: name });
  const width = name => row(name).locator('.po-ml-encoded-width');
  const resource = page.locator('.po-ml-resource-plan');
  await expect(row('TransactionID')).toContainText('Examples hidden for high-risk fields');
  await expect(row('event_type')).toContainText('Observed examples (2 of 2) "retail", "service"');
  await expect(width('TransactionID')).toHaveText('Estimated encoded columns: 25');
  await expect(width('amount')).toHaveText('Estimated encoded columns: 1');
  await expect(width('event_type')).toHaveText('Estimated encoded columns: 2');
  await expect(resource).toContainText('28 estimated encoded columns');

  const numeric = page.getByLabel('Numeric imputation method');
  const categorical = page.getByLabel('Categorical imputation method');
  await numeric.selectOption('mean');
  await categorical.selectOption('constant');
  await expect(width('event_type')).toHaveText('Estimated encoded columns: 3');
  await expect(resource).toContainText('29 estimated encoded columns');
  await page.locator('.feature-chip').filter({ hasText: 'TransactionID' }).getByRole('checkbox').check();
  await expect(width('TransactionID')).toHaveText('Estimated encoded columns: 0');
  await expect(resource).toContainText('4 estimated encoded columns');
  console.log('R05 Prepare category examples and per-field estimates: PASS');

  // The driver owns one bounded fit. The WebView itself only reads the saved record.
  const { id } = await post(project + '/experiments', {
    target: 'churn', task: 'classification', models: ['logistic_regression'],
    excluded_features: ['TransactionID'], acknowledge_random_split: true,
    expected_quality_version: 1, numeric_imputation: await numeric.inputValue(),
    categorical_imputation: await categorical.inputValue(),
  }, 202, 'queue one synthetic experiment');
  expect(id).toMatch(/^[0-9a-f]{32}$/);
  const experiment = `/experiments/${id}`;
  allowRead(experiment);
  await expect.poll(async () => (await get(experiment, 200, 'poll synthetic experiment')).status,
    { timeout: 30000 }).not.toMatch(/^(queued|running)$/);
  const saved = await get(experiment, 200, 'read completed fitted record');
  expect(saved).toMatchObject({ status: 'completed', dataset_version: 1, current_version: 1,
    config: { numeric_imputation: 'mean', categorical_imputation: 'constant', quality_version: 1 } });
  await post(experiment + '/select', { model_key: 'logistic_regression' }, 200, 'select fitted candidate');

  const navigation = page.getByRole('navigation', { name: 'Workspace navigation' });
  const recorded = page.getByRole('region', { name: 'Recorded experiment preprocessing' });
  async function reopen() {
    expect((await get(project, 200, 'verify one saved experiment')).experiments).toEqual([
      expect.objectContaining({ id, status: 'completed', selected_model: 'logistic_regression' }),
    ]);
    await openP4FixtureWorkspace(page, site, projectId);
    await expect(page.getByRole('combobox', { name: 'Switch project' })).toHaveValue(projectId);
    await navigation.getByRole('button', { name: 'Evaluate', exact: true }).click();
    await page.locator('button.mini-experiment').click();
    await expect(recorded).toContainText('Numeric missing values: Mean');
    await expect(recorded).toContainText('Categorical missing values: Reserved missing marker');
    await expect(recorded).toContainText('working data version v1');
  }

  await reopen();
  await page.getByRole('button', { name: 'Open Predict Studio' }).click();
  await expect(recorded).toContainText('working data version v1');
  await expect(page.getByRole('button', { name: 'Generate prediction' })).toBeEnabled();
  console.log('R05 fitted experiment reopened from project history: PASS');

  await applyQuality({ operation: 'restore', expected_version: 1, target_version: 0 }, 2);
  const stale = await get(experiment, 200, 'read historical fitted record');
  expect(stale).toMatchObject({ dataset_version: 1, current_version: 2, is_stale: true, config: saved.config });
  await reopen();
  await page.getByRole('button', { name: 'Open Predict Studio' }).click();
  await expect(page.getByText('This experiment was trained on a previous data version.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate prediction' })).toHaveCount(0);
  console.log('R05 historical settings and stale Predict guard: PASS');
}
