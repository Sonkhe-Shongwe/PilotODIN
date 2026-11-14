import { expect } from '@playwright/test';
import { p4PreparationRequestUrl } from './p4-preparation-request.mjs';

export const p4QualityFixture = [
  'churn,segment,amount',
  ...Array.from({ length: 80 }, (_, i) => [
    i % 2 ? 'Y' : 'N',
    i === 0 ? '" retail "' : i % 3 ? 'retail' : 'service',
    100 + i,
  ].join(',')),
].join('\n') + '\n';

export async function verifyP4QualityTransition(page, api, projectId, read, { beforeEdit, afterEdit } = {}) {
  const navigation = page.getByRole('navigation', { name: 'Workspace navigation' });
  const review = page.getByRole('region', { name: 'Potential prediction opportunities' });
  const target = page.getByLabel('TARGET VARIABLE');
  const planHeading = page.getByRole('heading', { name: 'Automatic preprocessing plan' });
  const chooser = page.getByRole('combobox', { name: 'Switch project' });
  const planV0 = p4PreparationRequestUrl(api, projectId, 'churn', 0);
  const planV1 = p4PreparationRequestUrl(api, projectId, 'churn', 1);
  const reviewV0 = `${api}/projects/${projectId}/target-opportunities?expected_version=0`;

  await expect(chooser).toHaveValue(projectId);
  await expect(review).toContainText('Current approved dataset version: 0.');
  await target.selectOption('churn');
  await expect(planHeading).toBeVisible();
  const before = await read(planV0);
  expect(before.status).toBe(200);
  expect(await before.json()).toMatchObject({ quality_version: 0, target: 'churn' });
  await beforeEdit?.();

  await navigation.getByRole('button', { name: 'Quality', exact: true }).click();
  await expect(page.getByText('WORKING VERSION 0', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Review 1 safe fixes', exact: true }).click();
  const approval = page.getByRole('dialog', { name: 'Review exact dataset change' });
  await expect(approval).toContainText('Working version: v0');
  await expect(approval).toContainText('Changed cells: 1');
  await expect(approval).toContainText('trim_whitespace');
  await expect(approval.getByRole('cell', { name: 'segment', exact: true })).toBeVisible();
  await approval.getByRole('button', { name: 'Approve these changes' }).click();
  await expect(approval).toHaveCount(0);
  await expect(page.getByText('WORKING VERSION 1', { exact: true })).toBeVisible();

  expect((await read(planV0)).status).toBe(409);
  expect((await read(reviewV0)).status).toBe(409);
  const after = await read(planV1);
  expect(after.status).toBe(200);
  expect(await after.json()).toMatchObject({ quality_version: 1, target: 'churn' });

  await navigation.getByRole('button', { name: 'Prepare', exact: true }).click();
  await expect(review).toContainText('Current approved dataset version: 1.');
  await expect(target).toHaveValue('churn');
  await expect(planHeading).toBeVisible();
  await afterEdit?.();

  await reloadP4SyntheticWorkspace(page);
  await expect(chooser).toHaveValue(projectId);
  await expect(review).toContainText('Current approved dataset version: 1.');
  await expect(target).toHaveValue('');
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url() === planV1 && r.request().method() === 'GET'),
    target.selectOption('churn'),
  ]);
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ quality_version: 1, target: 'churn' });
  await expect(planHeading).toBeVisible();
}

export async function reloadP4SyntheticWorkspace(page) {
  // Only the synthetic, in-memory target selection may be discarded by reload.
  const resolveReloadPrompt = dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss();
  page.on('dialog', resolveReloadPrompt);
  try {
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
  } finally {
    page.off('dialog', resolveReloadPrompt);
  }
}

export async function verifyP4QualityAfterRelaunch(page, api, projectId) {
  const chooser = page.getByRole('combobox', { name: 'Switch project' });
  const navigation = page.getByRole('navigation', { name: 'Workspace navigation' });
  const review = page.getByRole('region', { name: 'Potential prediction opportunities' });
  const target = page.getByLabel('TARGET VARIABLE');

  await expect(chooser).toHaveValue(projectId, { timeout: 45000 });
  await navigation.getByRole('button', { name: 'Prepare', exact: true }).click();
  await expect(review).toContainText('Current approved dataset version: 1.');
  await expect(target).toHaveValue('');
  const planV1 = p4PreparationRequestUrl(api, projectId, 'churn', 1);
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url() === planV1 && r.request().method() === 'GET', { timeout: 30000 }),
    target.selectOption('churn'),
  ]);
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ quality_version: 1, target: 'churn' });
  await expect(page.getByRole('heading', { name: 'Automatic preprocessing plan' })).toBeVisible();
}
