async (page) => {
  await page.setViewportSize({ width: 1920, height: 911 });
  await page.getByRole('heading', { name: '任务中心', exact: true }).waitFor();
  await page.waitForFunction(() => !Array.from(document.querySelectorAll('.hx-page .el-loading-mask')).some(e => e.getClientRects().length && getComputedStyle(e).display !== 'none'));
  const sizes = await page.locator('.hx-page .art-table').evaluate(root => {
    const names = ['.el-table', '.el-table__body-wrapper', '.el-scrollbar__wrap', '.el-table__empty-block', '.el-empty', '.el-empty__description'];
    return names.map(name => { const e = root.querySelector(name); const r = e.getBoundingClientRect(); return { name, top: r.top, bottom: r.bottom, height: r.height, overflow: getComputedStyle(e).overflow }; });
  });
  await page.screenshot({ path: 'output/playwright/table-layout-current.png' });
  return sizes;
}
