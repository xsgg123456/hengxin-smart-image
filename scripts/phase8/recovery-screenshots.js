async (page) => {
  const drawer = page.locator('.hx-detail.el-drawer');
  if (await drawer.isVisible()) {
    await drawer.locator('.el-drawer__close-btn').click();
    await drawer.waitFor({ state: 'hidden' });
  }
  const menu = page.getByRole('menuitem', { name: '替换文字', exact: true });
  if (!await menu.isVisible()) await page.locator('.el-sub-menu__title').filter({ hasText: '图片处理' }).first().click();
  await menu.click();
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  await page.getByRole('textbox', { name: '任务名称', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'output/playwright/phase8-auth-long-form.png', fullPage: true });
  await page.getByRole('button', { name: '查看已受理任务', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'output/playwright/phase8-auth-accepted.png', fullPage: true });
  return 'PHASE8 RECOVERY VISUAL PASS: long draft fields and accepted action scrolled into viewport';
}
