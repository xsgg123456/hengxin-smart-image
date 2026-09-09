async (page) => {
  const origin = page.url().split('/').slice(0, 3).join('/');
  const name = '认证恢复长名称' + '图'.repeat(53);
  const note = '完整保留原始修改意见与素材，恢复同一用户的同一次提交。';
  const requests = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let first = true, receipt, failDetail = false;
  for (const [mode, heading] of [['wallpaper', '替换壁纸'], ['product', '替换商品'], ['text', '替换文字'], ['templates/index', '模板库']]) {
    await page.goto(origin + '/#/' + (mode.includes('/') ? mode : 'image-processing/' + mode));
    await page.getByRole('heading', { name: heading, exact: true }).waitFor();
    await page.waitForFunction(() => !Array.from(document.querySelectorAll('.el-loading-mask,.el-message')).some(e => e.getClientRects().length));
    await page.waitForFunction(() => Array.from(document.querySelectorAll('.hx-page img')).filter(e => e.getClientRects().length).every(e => e.complete && e.naturalWidth > 0));
    await page.screenshot({ path: 'output/playwright/phase8-' + mode.replace('/', '-') + '.png', fullPage: true });
  }
  await page.goto(origin + '/#/image-processing/text');
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  if (await page.getByRole('button', { name: '另建任务', exact: true }).isVisible()) {
    await page.getByRole('button', { name: '另建任务', exact: true }).click();
  }
  await page.locator('input[type=file]').setInputFiles('output/playwright/phase8-pixel.png');
  await page.getByRole('textbox', { name: '任务名称', exact: true }).fill(name);
  await page.getByRole('textbox', { name: 'SKU', exact: true }).fill('SKU-' + '8'.repeat(76));
  await page.getByRole('textbox', { name: '修改要求', exact: true }).fill(note);
  await page.route('**/api/v1/tasks', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    requests.push({ key: route.request().headers()['idempotency-key'], body: route.request().postData() });
    if (!first) return route.continue();
    first = false;
    const response = await route.fetch();
    if (response.status() !== 202) throw Error(await response.text());
    receipt = await response.json();
    await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ code: 'UNAUTHORIZED', message: '集成测试：受理回执丢失后重新认证' }) });
  });
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(e => e.textContent.includes('提交生成任务') && !e.disabled));
  await page.getByRole('button', { name: '提交生成任务', exact: true }).click();
  await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).click();
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  if (await page.getByRole('textbox', { name: '任务名称', exact: true }).inputValue() !== name) throw Error('401恢复丢失任务名称');
  if (await page.getByRole('textbox', { name: '修改要求', exact: true }).inputValue() !== note) throw Error('401恢复丢失意见');
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.waitForFunction(() => !Array.from(document.querySelectorAll('.el-loading-mask,.el-message')).some(e => e.getClientRects().length));
  await page.screenshot({ path: 'output/playwright/phase8-auth-recovery.png', fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw Error('长名称恢复页面横向溢出');
  await page.route('**/api/v1/tasks/*', async route => {
    if (failDetail && route.request().method() === 'GET' && route.request().url().endsWith('/' + receipt.taskId)) {
      failDetail = false;
      return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ code: 'UNAUTHORIZED', message: '集成测试：详情读取需要重新认证' }) });
    }
    return route.continue();
  });
  failDetail = true;
  await page.getByRole('button', { name: '确认上次提交', exact: true }).click();
  await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).click();
  await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
  if (requests.length !== 2 || requests[0].key !== requests[1].key || requests[0].body !== requests[1].body) throw Error('401后更换了幂等键或原快照');
  const drawer = page.locator('.hx-detail.el-drawer');
  if (await drawer.isVisible()) {
    await drawer.locator('.el-drawer__close-btn').click();
    await drawer.waitFor({ state: 'hidden' });
  }
  const textMenu = page.getByRole('menuitem', { name: '替换文字', exact: true });
  if (!await textMenu.isVisible()) await page.locator('.el-sub-menu__title').filter({ hasText: '图片处理' }).first().click();
  await textMenu.click();
  await page.getByRole('button', { name: '查看已受理任务', exact: true }).waitFor();
  await page.getByText('任务已受理：' + receipt.taskId, { exact: true }).waitFor();
  await page.getByRole('button', { name: '查看已受理任务', exact: true }).click();
  await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
  if (requests.length !== 2) throw Error('查看原回执重复POST');
  const tasks = await (await page.request.get(origin + '/api/v1/tasks?search=' + encodeURIComponent(name))).json();
  if (tasks.total !== 1 || tasks.items[0].id !== receipt.taskId) throw Error('认证恢复重复创建了任务');
  let completed = false;
  for (let attempt = 0; attempt < 90; attempt++) {
    const data = await (await page.request.get(origin + '/api/v1/tasks/' + receipt.taskId)).json();
    if (data.task.state === '失败') throw Error('认证任务执行失败：' + JSON.stringify(data));
    if (data.task.state === '待查看') { completed = true; break; }
    await page.waitForTimeout(1000);
  }
  if (!completed) throw Error('认证任务未完成，不能开始独立Worker故障场景');
  await page.unroute('**/api/v1/tasks');
  await page.unroute('**/api/v1/tasks/*');
  if (errors.length) throw Error(errors.join('\n'));
  return 'PHASE8 AUTH RECOVERY PASS: real accepted POST masked by401, same identity reconnect retains60char draft, same key/body replay, accepted GET401 retains receipt, view original creates no extra task';
}
