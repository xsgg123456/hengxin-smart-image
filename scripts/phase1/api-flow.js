async (page) => {
  await page.goto('http://127.0.0.1:3008/#/image-processing/wallpaper');
  await page.reload();
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: 'output/playwright/frontend-wallpaper.png', fullPage: true });
  await page.goto('http://127.0.0.1:3018/#/image-processing/wallpaper');
  await page.getByRole('button', { name: '重新连接', exact: true }).waitFor();
  if (await page.getByRole('menuitem', { name: '模板库', exact: true }).count()) throw new Error('断连显示了工作区');
  await page.getByRole('button', { name: '重新连接', exact: true }).click();
  await page.getByRole('button', { name: '重新连接', exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/api-disconnected.png', fullPage: true });
  return 'PASS: 真实接口断连与重试均阻断工作区，无模拟回退';
}
