async (page) => {
  await page.goto('http://127.0.0.1:3008/#/templates/index');
  await page.getByRole('button', { name: '新建模板', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '新建套图模板', exact: true });
  await dialog.getByRole('button', { name: '保存模板', exact: true }).click();
  await page.getByText('请填写模板名称并添加图片', { exact: true }).waitFor();
  await dialog.getByRole('textbox', { name: '*模板名称', exact: true }).fill('Phase1 模板保存');
  await dialog.getByRole('button', { name: '使用示例套图', exact: true }).click();
  await dialog.getByRole('button', { name: '保存模板', exact: true }).click();
  await dialog.waitFor({ state: 'hidden' });
  await page.getByRole('heading', { name: 'Phase1 模板保存', exact: true }).waitFor();
  await page.getByRole('textbox', { name: '搜索模板名称' }).fill('不存在的模板789');
  await page.getByText('暂无匹配模板，可新建或清除筛选').waitFor();
  await page.getByRole('textbox', { name: '搜索模板名称' }).fill('');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(1800);
  await page.screenshot({ path: 'output/playwright/templates.png', fullPage: true });
  await page.goto('http://127.0.0.1:3008/#/image-processing/wallpaper');
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: 'output/playwright/frontend-wallpaper.png', fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('页面横向溢出');
  await page.goto('http://127.0.0.1:3007/#/image-processing/wallpaper');
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: 'output/playwright/prototype-wallpaper.png', fullPage: true });
  return 'PASS: 模板校验/保存、搜索空状态、1440px无横向溢出、正式/原型截图';
}
