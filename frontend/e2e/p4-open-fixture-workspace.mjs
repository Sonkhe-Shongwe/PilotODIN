// Start with a new document so an already-mounted empty catalogue is refreshed.
export async function openP4FixtureWorkspace(page, origin, projectId) {
  const prepareUrl = new URL('/?p4-fixture=prepare#/studio/prepare', origin);
  await page.evaluate(id => {
    localStorage.setItem('pilotodin-current', id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-' + id, JSON.stringify(['prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-' + id, 'prepare');
  }, projectId);
  await page.goto(prepareUrl.href, { waitUntil: 'domcontentloaded' });
}
