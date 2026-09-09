async (page) => {
  const origin = 'http://127.0.0.1:3008';
  const measurements = [];
  async function checkEmpty(label) {
    await page.locator('.hx-page .art-table .el-empty__description').scrollIntoViewIfNeeded();
    const result = await page.locator('.hx-page .art-table').evaluate(root => {
      const body = root.querySelector('.el-table__body-wrapper').getBoundingClientRect();
      const empty = root.querySelector('.el-empty').getBoundingClientRect();
      const text = root.querySelector('.el-empty__description').getBoundingClientRect();
      const pagination = root.parentElement.querySelector('.el-pagination');
      const paginationClear = !pagination || pagination.getBoundingClientRect().top >= root.querySelector('.el-table').getBoundingClientRect().bottom;
      return { bodyHeight: body.height, emptyHeight: empty.height, paginationClear, contained: paginationClear && empty.top >= body.top - 1 && empty.bottom <= body.bottom + 1 && text.bottom <= body.bottom + 1 };
    });
    if (!result.contained) throw Error(label + ': clipped ' + JSON.stringify(result));
    measurements.push({ label, ...result });
    await page.screenshot({ path: 'output/playwright/table-layout-' + label + '.png' });
  }
  for (const width of [1920, 1024]) {
    await page.setViewportSize({ width, height: 911 });
    await page.goto(origin + '/#/tasks/index');
    await page.getByText('暂无匹配任务', { exact: true }).waitFor();
    await checkEmpty('empty-' + width);
  }
  // Browser-only GET fixtures; no development database writes.
  for (const width of [1920, 1024]) {
  await page.setViewportSize({ width, height: 911 });
  let release;
  const blocked = new Promise(resolve => { release = resolve; });
  await page.route('**/api/v1/tasks?*', async route => {
    await blocked;
    const items = Array.from({ length: 2 }, (_, i) => ({ id: 'layout-' + i, name: '布局验证行' + i, mode: 'text', template: '', skillVersionId: 'fixture', ownerId: 'fixture', sessionId: null, state: '排队中', progress: null, images: [], sources: [], feedback: [], time: '2026-09-09T00:00:00Z', archived: false, currentRoundId: 'round-' + i, executionSource: 'fixture' }));
    await route.fulfill({ json: { items, page: 1, pageSize: 12, total: 2, stats: { total: 2, processing: 2, ready: 0, archived: 0 } } });
  });
  await page.reload();
  await page.locator('.hx-page .art-table .el-loading-mask').waitFor({ state: 'visible' });
  measurements.push({ label: 'loading-' + width, visible: true });
  release();
  await page.getByText('布局验证行1', { exact: true }).waitFor();
  const rows = await page.locator('.hx-page .art-table').evaluate(root => {
    const body = root.querySelector('.el-table__body-wrapper').getBoundingClientRect();
    const pagination = root.parentElement.querySelector('.el-pagination').getBoundingClientRect();
    return pagination.top >= root.querySelector('.el-table').getBoundingClientRect().bottom && [...root.querySelectorAll('.el-table__row')].every(e => { const r = e.getBoundingClientRect(); return r.top >= body.top - 1 && r.bottom <= body.bottom + 1; });
  });
  if (!rows) throw Error('data rows clipped');
  measurements.push({ label: 'data-' + width, rows: 2, contained: rows });
  await page.screenshot({ path: 'output/playwright/table-layout-data-' + width + '.png' });
  await page.unroute('**/api/v1/tasks?*');
  }
  await page.route('**/api/v1/auth/me', async route => { const response = await route.fetch(); const user = await response.json(); await route.fulfill({ json: { ...user, role: 'super_admin' } }); });
  await page.route('**/api/v1/management/skills', route => route.fulfill({ json: [] }));
  await page.goto(origin + '/#/management/skills');
  await page.reload();
  await page.getByText('暂无 Skill，请上传版本包', { exact: true }).waitFor();
  await checkEmpty('skills-neighbor');
  await page.unrouteAll({ behavior: 'wait' });
  return { result: 'TABLE LAYOUT PASS', measurements };
}
