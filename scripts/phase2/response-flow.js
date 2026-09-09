async (page) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let scenario = 'malformed';
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', route => {
    const path = route.request().url();
    const user = { id: 'test-only-user', name: '测试身份', role: 'operator', status: scenario === 'disabled' ? 'disabled' : 'active' };
    const body = path.endsWith('/auth/me') ? user : path.includes('/templates?') ? {items:[],page:1,pageSize:4,total:0} : path.includes('/skills') ? [] : scenario === 'malformed' ? { templates: [null], tasks: [], archives: [] } : { templates: [], tasks: [], archives: [] };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.goto('http://127.0.0.1:3018/#/image-processing/wallpaper');
  await page.reload();
  await page.getByText('服务返回的数据不完整，请稍后重试', { exact: true }).waitFor();
  scenario = 'disabled';
  await page.getByRole('button', { name: '重新连接', exact: true }).click();
  await page.getByText('账号未授权或已禁用', { exact: true }).waitFor();
  scenario = 'empty';
  await page.getByRole('button', { name: '重新连接', exact: true }).click();
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.getByText('暂无匹配的可用模板，请清除搜索或先创建模板', { exact: true }).waitFor();
  if (await page.getByRole('button', { name: '使用示例素材', exact: true }).count()) throw new Error('真实模式出现示例素材');
  if (errors.length) throw new Error(errors.join(';'));
  await page.unroute('**/api/v1/**');
  await page.goto('http://127.0.0.1:3008/#/image-processing/product');
  await page.getByRole('heading', { name: '替换商品', exact: true }).waitFor();
  await page.getByRole('menuitem', { name: '替换文字', exact: true }).click();
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.waitForTimeout(600);
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('1280px横向溢出');
  return 'PASS: 畸形数据错误、禁用用户阻断、重新连接恢复、真实空状态无样例入口、商品/文字导航、1280px无溢出，pageerror=0';
}
