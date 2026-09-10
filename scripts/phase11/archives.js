async (page) => {
  const origin = page.url().split('/').slice(0, 3).join('/'), api = origin + '/api/v1';
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const seed = (await (await page.request.get(api + '/tasks?search=phase8-duplicate-limit2')).json()).items[0];
  if (!seed) throw Error('Missing isolated fixture task');
  const response = await page.request.post(api + '/tasks', {
    headers: { 'Idempotency-Key': 'phase11-browser-' + Date.now() },
    data: { mode: 'text', name: 'Phase11归档验证', sources: [...seed.sources, ...seed.sources],
      skillVersionId: seed.skillVersionId, note: '隔离归档测试' }
  });
  if (response.status() !== 202) throw Error(await response.text());
  const receipt = await response.json(), path = api + '/tasks/' + receipt.taskId;
  const completed = async () => {
    for (let i = 0; i < 90; i++) {
      const data = await (await page.request.get(path)).json();
      if (data.task.state === '待查看') return data;
      if (['失败', '部分失败'].includes(data.task.state)) throw Error(JSON.stringify(data));
      await page.waitForTimeout(1000);
    }
    throw Error('Task did not finish');
  };
  const initial = await completed();
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(origin + '/#/tasks/index?taskId=' + receipt.taskId);
  const drawer = page.locator('.hx-detail.el-drawer');
  await drawer.getByText('待查看', { exact: true }).waitFor();
  const archiveUrl = path + '/archives', actions = [];
  page.on('request', request => {
    if (request.url() === archiveUrl && request.method() === 'POST') {
      actions.push({ body: request.postDataJSON(), key: request.headers()['idempotency-key'] });
    }
  });
  let saved;
  await page.route(archiveUrl, async route => {
    const result = await route.fetch();
    if (result.status() !== 200) throw Error(await result.text());
    saved = await result.json();
    await route.abort('failed');
  }, { times: 1 });
  await drawer.getByRole('button', { name: '归档到成品库', exact: true }).click();
  await drawer.getByText('服务连接失败，请检查网络或稍后重试', { exact: true }).waitFor();
  const archived = page.waitForResponse(r => r.url() === archiveUrl && r.status() === 200);
  await drawer.getByRole('button', { name: /归档到成品库|再次归档当前整套/ }).click();
  const replay = await (await archived).json();
  if (!saved || saved.id !== replay.id || !actions[0].key || JSON.stringify(actions[0]) !== JSON.stringify(actions[1])) {
    throw Error('Lost archive response did not replay its original action');
  }
  if ((await (await page.request.get(api + '/archives?search=Phase11归档验证')).json()).total !== 1) throw Error('Duplicate archive');
  const oldBytes = await Promise.all(saved.images.map(async p => (await page.request.get(origin + p.url)).body()));
  const revision = await page.request.post(path + '/rounds', {
    headers: { 'Idempotency-Key': 'phase11-revise-' + Date.now() },
    data: { taskId: receipt.taskId, target: 0, note: '归档后返工' }
  });
  if (revision.status() !== 202) throw Error(await revision.text());
  const blocked = await page.request.post(archiveUrl);
  if (blocked.status() !== 409) throw Error('Running task archived');
  const updated = await completed();
  if (updated.slots[0].currentVersionId === initial.slots[0].currentVersionId) throw Error('Revision did not create version');
  const oldArchive = await (await page.request.get(api + '/archives/' + saved.id)).json();
  if (JSON.stringify(oldArchive) !== JSON.stringify(saved)) throw Error('Archive mutated after revision');
  for (let i = 0; i < saved.images.length; i++) {
    const bytes = await (await page.request.get(origin + saved.images[i].url)).body();
    if (Array.from(bytes).join(',') !== Array.from(oldBytes[i]).join(',')) throw Error('Archived bytes changed');
  }
  await page.goto(origin + '/#/archive/index');
  await page.getByRole('heading', { name: '成品库', exact: true }).waitFor();
  const search = page.getByRole('textbox', { name: '搜索成品名称', exact: true });
  await search.fill('Phase11归档验证');
  const card = page.locator('.hx-library-card').filter({ hasText: 'Phase11归档验证' });
  await card.getByRole('button', { name: '查看成品', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Phase11归档验证', exact: true });
  await dialog.getByText('归档图片 · 后续修改不会覆盖此版本', { exact: true }).waitFor();
  await page.waitForFunction(() => [...document.querySelectorAll('.el-dialog .el-image img')].length === 2 &&
    [...document.querySelectorAll('.el-dialog .el-image img')].every(img => img.complete && img.naturalWidth > 0));
  const one = page.waitForEvent('download');
  await dialog.getByRole('button', { name: '下载图片', exact: true }).first().click();
  await (await one).saveAs('output/playwright/phase11-single.png');
  await dialog.locator('.el-dialog__headerbtn').click();
  const zip = page.waitForEvent('download');
  await card.getByRole('button', { name: '下载整套', exact: true }).click();
  await (await zip).saveAs('output/playwright/phase11-archive.zip');
  await page.setViewportSize({ width: 1024, height: 768 });
  await card.getByRole('button', { name: '查看成品', exact: true }).waitFor();
  // Visible controls must stay inside every clipping ancestor, not just the document width.
  const clipped = await card.locator('button, h3, p').evaluateAll(nodes => nodes.some(node => {
    const r = node.getBoundingClientRect();
    for (let p = node.parentElement; p; p = p.parentElement) {
      const style = getComputedStyle(p), box = p.getBoundingClientRect();
      if (/(hidden|clip|auto|scroll)/.test(style.overflowX) && (r.left < box.left - 1 || r.right > box.right + 1)) return true;
      if (/(hidden|clip)/.test(style.overflowY) && (r.top < box.top - 1 || r.bottom > box.bottom + 1)) return true;
    }
    return false;
  }));
  if (clipped) throw Error('Archive controls clipped');
  await page.screenshot({ path: 'output/playwright/phase11-archives.png', fullPage: true });
  await page.route('**/api/v1/archives?*', route => route.fulfill({ status: 503,
    contentType: 'application/json', body: JSON.stringify({ code: 'UNAVAILABLE', message: '隔离测试成品加载失败' }) }), { times: 1 });
  await search.fill('触发错误');
  await page.getByText('隔离测试成品加载失败', { exact: true }).waitFor();
  await page.getByRole('button', { name: '重试加载', exact: true }).click();
  await page.getByText('暂无匹配成品，可清除筛选或归档任务结果', { exact: true }).waitFor();
  await search.fill('Phase11归档验证');
  await card.getByRole('button', { name: '删除成品', exact: true }).click();
  await page.getByRole('button', { name: '确认删除', exact: true }).click();
  await card.waitFor({ state: 'detached' });
  if ((await page.request.get(api + '/archives/' + saved.id)).status() !== 404) throw Error('Archive deletion not persisted');
  if ((await page.request.get(path)).status() !== 200) throw Error('Archive deletion removed task');
  if ((await page.request.get(origin + saved.images[0].url)).status() !== 200) throw Error('Archive deletion removed referenced image');
  if (errors.length) throw Error(errors.join('\n'));
  return 'PHASE11 BROWSER PASS: archive lost-response replay, revision preserves snapshot/bytes, old-version preview, single/streaming ZIP download, error/empty/retry, deletion reference protection; pageerrors=0';
}
