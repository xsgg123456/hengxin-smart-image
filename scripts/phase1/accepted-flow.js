async (page) => {
  let posts = 0, reads = 0, failRead = false;
  const picture = { name: '预览图片', url: '/samples/wallpaper-0.svg', version: 1 };
  const template = { id: 't1', name: '测试模板', mode: 'wallpaper', images: [picture], skill: '测试 Skill', active: true, version: 1, ownerId: 'test-user' };
  const workspace = { templates: [template], tasks: [], archives: [] };
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', route => {
    const url = route.request().url();
    if (url.endsWith('/auth/me')) return route.fulfill({ json: { id: 'test-user', name: '测试身份', role: 'operator', status: 'active' } });
    if (url.endsWith('/tasks') && route.request().method() === 'POST') {
      posts++; failRead = true;
      return route.fulfill({ status: 202, json: { taskId: 'accepted-task', roundId: 'r1', state: '排队中' } });
    }
    if (url.endsWith('/workspace')) {
      reads++;
      return failRead ? route.fulfill({ status: 503, json: { code: 'UNAVAILABLE', message: '工作区读取失败' } }) : route.fulfill({ json: workspace });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('http://127.0.0.1:3018/#/image-processing/wallpaper');
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.getByRole('button', { name: '提交生成任务', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: '请先上传素材' }).first().waitFor();
  if (await page.getByText('请先上传素材或使用示例素材', { exact: true }).count()) throw new Error('真实模式死引导');
  await page.locator('input[type=file]').setInputFiles('output/playwright/pixel.png');
  await page.getByRole('textbox', { name: '*任务名称', exact: true }).fill('受理成功读取失败');
  await page.getByRole('button', { name: '提交生成任务', exact: true }).click();
  await page.waitForURL('**task=accepted-task');
  await page.getByText('工作区读取失败', { exact: true }).waitFor();
  if (posts !== 1) throw new Error('重复提交');
  failRead = false;
  await page.getByRole('button', { name: '重新加载', exact: true }).click();
  await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
  const before = reads;
  await page.waitForTimeout(1600);
  if (reads <= before) throw new Error('任务页未轮询');
  await page.getByRole('menuitem', { name: '模板库', exact: true }).click();
  const left = reads;
  await page.waitForTimeout(3500);
  if (reads !== left) throw new Error('离开任务页仍轮询');
  if (posts !== 1) throw new Error('恢复读取触发重复写入');
  await page.unroute('**/api/v1/**');
  return 'PASS: HTTP受理成功后读取失败保留taskId且只提交一次；读取重试不重复写入；任务页轮询/离页停止';
}
