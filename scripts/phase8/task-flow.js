async (page) => {
  const origin = page.url().split('/').slice(0, 3).join('/');
  const errors = [], receipts = [];
  page.on('pageerror', error => errors.push(error.message));
  const stable = () => page.waitForFunction(() => !Array.from(document.querySelectorAll('.el-loading-mask, .el-message')).some(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'));
  for (const [mode, title] of [['wallpaper', '替换壁纸'], ['product', '替换商品'], ['text', '替换文字']]) {
    await page.goto(origin + '/#/image-processing/' + mode);
    await page.getByRole('heading', { name: title, exact: true }).waitFor();
    if (mode !== 'text') await page.locator('.hx-template-option').filter({ hasText: 'phase8-' + mode }).click();
    await page.locator('input[type=file]').setInputFiles('output/playwright/phase8-pixel.png');
    await page.getByRole('textbox', { name: '任务名称', exact: true }).fill('浏览器-' + mode);
    await page.getByRole('textbox', { name: '修改要求', exact: true }).fill('保留布局的隔离执行测试');
    await page.getByRole('button', { name: '提交生成任务', exact: true }).waitFor();
    await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some(e => e.textContent.includes('提交生成任务') && !e.disabled));
    const accepted = page.waitForResponse(r => r.url().endsWith('/tasks') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '提交生成任务', exact: true }).click();
    const response = await accepted;
    if (response.status() !== 202) throw Error(await response.text());
    if (!response.request().headers()['idempotency-key']) throw Error('UI未传幂等键');
    receipts.push(await response.json());
    await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
    await page.goto('about:blank');
  }
  for (const receipt of receipts) {
    let complete = false;
    for (let attempt = 0; attempt < 90; attempt++) {
      const response = await page.request.get(origin + '/api/v1/tasks/' + receipt.taskId);
      const data = await response.json();
      if (data.task.state === '失败') throw Error(JSON.stringify(data));
      if (data.task.state === '待查看') { complete = true; break; }
      await page.waitForTimeout(1000);
    }
    if (!complete) throw Error('离开页面后后台任务未完成');
  }
  await page.goto(origin + '/#/tasks/index?taskId=' + receipts[2].taskId);
  await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
  const drawer = page.locator('.hx-detail.el-drawer');
  await drawer.getByText('待查看', { exact: true }).waitFor();
  await drawer.getByText(/测试执行器/).first().waitFor();
  if (!(await drawer.getByRole('button', { name: '整套修改', exact: true }).isEnabled())) throw Error('成功任务未开放返工');
  const download = page.waitForEvent('download');
  await drawer.getByRole('button', { name: '下载整套', exact: true }).click();
  await (await download).saveAs('output/playwright/phase8-results.zip');
  await stable();
  await page.screenshot({ path: 'output/playwright/phase8-detail.png', fullPage: true });
  await drawer.locator('.el-drawer__close-btn').click();
  await drawer.waitFor({ state: 'hidden' });
  await page.goto(origin + '/#/tasks/index');
  await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill('浏览器-text');
  const row = page.getByRole('row').filter({ hasText: '浏览器-text' });
  await row.getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('button', { name: '确认删除', exact: true }).click();
  await row.waitFor({ state: 'detached' });
  if ((await page.request.get(origin + '/api/v1/tasks/' + receipts[2].taskId)).status() !== 404) throw Error('删除未落库');
  await page.setViewportSize({ width: 1024, height: 768 });
  await stable();
  await page.screenshot({ path: 'output/playwright/phase8-tasks.png', fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw Error('任务页面横向溢出');
  if (errors.length) throw Error(errors.join('\n'));
  return 'PHASE8 BROWSER PASS: three real submissions, idempotency headers, background completion after leaving page, fixture label, executionControl, download, delete; pageerrors=0';
}
