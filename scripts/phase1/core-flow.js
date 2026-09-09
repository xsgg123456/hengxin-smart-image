async (page) => {
  await page.goto('http://127.0.0.1:3008/#/image-processing/wallpaper');
  await page.reload();
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor();
  await page.getByText('前端模拟预览 · 生成返回示例图片，数据仅在本次页面打开期间保留，刷新后重置。').waitFor();
  await page.getByRole('button', { name: '提交生成任务' }).click();
  await page.getByRole('alert').filter({ hasText: '请先上传素材或使用示例素材' }).first().waitFor();
  await page.getByRole('button', { name: '使用示例素材' }).click();
  await page.getByRole('textbox', { name: '*任务名称', exact: true }).fill('Phase1 浏览器验收');
  await page.getByRole('button', { name: '提交生成任务' }).click();
  const drawer = page.getByRole('dialog', { name: 'Phase1 浏览器验收', exact: true });
  await drawer.waitFor();
  await drawer.getByRole('button', { name: '修改这张', exact: true }).nth(1).click();
  const feedback = page.getByRole('dialog', { name: '修改第 2 张图片', exact: true });
  await feedback.getByRole('textbox').fill('只调整第二张，保持其他图片');
  await feedback.getByRole('button', { name: '提交修改' }).click();
  await feedback.waitFor({ state: 'hidden' });
  await drawer.getByText('v2', { exact: true }).waitFor();
  if (await drawer.getByText('v1', { exact: true }).count() !== 7) throw new Error('非目标图片版本被改动');
  await drawer.getByRole('button', { name: '归档到成品库', exact: true }).click();
  await drawer.getByRole('button', { name: '已归档', exact: true }).waitFor();
  await drawer.getByRole('button', { name: '关闭此对话框', exact: true }).click();
  await page.getByRole('menuitem', { name: '成品库', exact: true }).click();
  await page.getByRole('heading', { name: 'Phase1 浏览器验收', exact: true }).waitFor();
  return ('PASS: 校验 -> 创建 -> 单图返工(v2/其余7张v1) -> 归档 -> 成品库');
}
