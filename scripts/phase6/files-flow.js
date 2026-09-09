async (page) => {
  const origin = page.url().split('/').slice(0, 3).join('/');
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let workspaceCalls = 0;
  page.on('request', request => { if (request.url().endsWith('/api/v1/workspace')) workspaceCalls++; });
  await page.goto(origin + '/?role=super_admin#/image-processing/text');
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  const identity = await (await page.request.get(origin + '/api/v1/auth/me')).json();
  if (identity.role !== 'operator') throw Error('客户端查询参数伪造身份');
  if (await page.getByRole('button', { name: '使用示例素材' }).count()) throw Error('真实模式显示模拟素材');
  await page.getByRole('textbox', { name: '任务名称', exact: true }).fill('真实上传失败重试');
  await page.getByRole('textbox', { name: '修改要求', exact: true }).fill('保留这段修改意见');
  let fail = true;
  await page.route('**/api/v1/files', route => {
    if (fail && route.request().method() === 'POST') {
      fail = false;
      return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'STORAGE_UNAVAILABLE', message: '测试上传服务暂不可用' }) });
    }
    return route.continue();
  });
  const pixel = 'output/playwright/phase6-pixel.png';
  const originalBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg==';
  await page.locator('input[type=file]').setInputFiles(pixel);
  await page.getByRole('button', { name: '重试图片 1', exact: true }).waitFor();
  if (await page.getByRole('textbox', { name: '任务名称', exact: true }).inputValue() !== '真实上传失败重试') throw Error('上传失败丢失名称');
  const received = page.waitForResponse(r => r.url().endsWith('/api/v1/files') && r.request().method() === 'POST' && r.status() === 200);
  await page.getByRole('button', { name: '重试图片 1', exact: true }).click();
  const picture = await (await received).json();
  await page.getByText('已接收', { exact: true }).waitFor();
  if (!picture.fileId || !picture.url.startsWith('/api/v1/files/')) throw Error('不是持久化文件引用');
  const data = await page.request.get(origin + picture.url);
  if (!data.ok() || (await data.body()).toString('base64') !== originalBase64) throw Error('预览字节不等于原图');
  await page.locator('.hx-source .el-image').click();
  await page.locator('.el-image-viewer__wrapper').waitFor();
  await page.keyboard.press('Escape');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载图片 1', exact: true }).click();
  const download = await downloadPromise;
  if (await download.failure()) throw Error('下载失败');
  if (!download.suggestedFilename().endsWith('.png')) throw Error('下载格式改变');
  if (!await page.getByRole('button', { name: '提交生成任务' }).isDisabled()) throw Error('未接Skill仍能生成');
  if (await page.getByRole('textbox', { name: '修改要求', exact: true }).inputValue() !== '保留这段修改意见') throw Error('重试丢失意见');
  await page.locator('input[type=file]').setInputFiles('hengxin-smart-image/frontend/tests/fixtures/jpeg-with-trailer.jpg');
  await page.getByRole('button', { name: '下载图片 2', exact: true }).waitFor();
  const jpegDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载图片 2', exact: true }).click();
  await (await jpegDownload).saveAs('output/playwright/phase6-jpeg-download.jpg');
  await page.getByRole('heading', { name: '替换文字', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'output/playwright/phase6-real-upload.png', fullPage: true });
  await page.reload();
  await page.getByRole('heading', { name: '替换文字', exact: true }).waitFor();
  const after = await page.request.get(origin + '/api/v1/files/' + picture.fileId);
  if (!after.ok() || (await after.json()).fileId !== picture.fileId) throw Error('刷新丢失服务器素材');
  if ((await (await page.request.get(origin + picture.url)).body()).toString('base64') !== originalBase64) throw Error('刷新后原图变化');
  await page.unrouteAll();
  // 三入口均能上传，模板/Skill 的501不阻断素材区。
  for (const mode of ['wallpaper', 'product']) {
    await page.goto(origin + '/#/image-processing/' + mode);
    await page.getByRole('heading', { name: mode === 'wallpaper' ? '替换壁纸' : '替换商品', exact: true }).waitFor();
    await page.locator('input[type=file]').setInputFiles(pixel);
    await page.getByText('已接收', { exact: true }).waitFor();
    if (!await page.getByRole('button', { name: '提交生成任务' }).isDisabled()) throw Error('模板未接入仍可生成');
    await page.getByRole('button', { name: '移除图片 1', exact: true }).click();
    if (await page.getByText('已接收', { exact: true }).count()) throw Error('移除选择失败');
  }
  await page.locator('input[type=file]').setInputFiles(Array(21).fill(pixel));
  await page.getByText('phase6-pixel.png：每组最多 20 张，请移除图片后再添加', { exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelectorAll('.picture-meta small').length === 20 && Array.from(document.querySelectorAll('.picture-meta small')).every(x => x.textContent === '已接收'));
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({ path: 'output/playwright/phase6-narrow-upload.png', fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw Error('窄视口横向溢出');
  if (workspaceCalls) throw Error('真实启动仍依赖全量workspace');
  if (errors.length) throw Error(errors.join('\n'));
  return 'PHASE6 BROWSER PASS: real upload/preview/download, failure retry preserves input, reload persistence, three modes, 20-image limit, no fake identity, pageerror=0';
}
