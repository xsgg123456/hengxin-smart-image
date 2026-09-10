async (page) => {
  const origin = page.url().split('/').slice(0, 3).join('/');
  const errors = [], submissions = [];
  page.on('pageerror', error => errors.push(error.message));
  const api = origin + '/api/v1';
  const seed = (await (await page.request.get(api + '/tasks?search=phase10-api')).json()).items[0];
  if (!seed) throw Error('Run --phase10 API checks before browser checks');
  const created = await page.request.post(api + '/tasks', {
    headers: { 'Idempotency-Key': 'phase10-browser-' + Date.now() },
    data: { mode: 'text', name: 'Phase10浏览器返工', sources: seed.sources,
      skillVersionId: seed.skillVersionId, note: '浏览器双图初始生成' }
  });
  if (created.status() !== 202) throw Error(await created.text());
  const receipt = await created.json();
  const path = api + '/tasks/' + receipt.taskId;
  const detail = async () => (await page.request.get(path)).json();
  const completed = async () => {
    for (let attempt = 0; attempt < 80; attempt++) {
      const data = await detail();
      if (['失败', '部分失败'].includes(data.task.state)) throw Error(JSON.stringify(data));
      if (data.task.state === '待查看') return data;
      await page.waitForTimeout(1000);
    }
    throw Error('离开页面后返工未完成');
  };
  const open = async () => {
    await page.goto(origin + '/#/tasks/index?taskId=' + receipt.taskId);
    await page.locator('.hx-detail.el-drawer').getByText('待查看', { exact: true }).waitFor();
  };
  const before = await completed();
  await open();
  const drawer = page.locator('.hx-detail.el-drawer');
  const cards = drawer.locator('.hx-result-grid > .el-card');
  const editOne = () => cards.nth(1).getByRole('button', { name: '修改这张', exact: true }).click();
  const feedback = page.getByPlaceholder('填写本轮修改意见');
  const submit = page.getByRole('button', { name: '提交修改', exact: true });
  const revisionUrl = path + '/rounds';
  page.on('request', request => {
    if (request.url() === revisionUrl && request.method() === 'POST') {
      submissions.push({ key: request.headers()['idempotency-key'], body: request.postDataJSON() });
    }
  });
  // A controlled server conflict exercises the real UI's error/draft recovery path.
  await page.route(revisionUrl, route => route.fulfill({ status: 409,
    contentType: 'application/json', body: JSON.stringify({ code: 'CONFLICT', message: '测试竞争冲突：意见已保留' }) }), { times: 1 });
  await editOne();
  const singleNote = '只调整第二张文字，其他位置保持不变';
  await feedback.fill(singleNote);
  await submit.click();
  await page.getByText('测试竞争冲突：意见已保留', { exact: true }).first().waitFor();
  if (await feedback.inputValue() !== singleNote) throw Error('409丢失意见');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await editOne();
  if (await feedback.inputValue() !== singleNote) throw Error('关闭重开丢失意见');
  const acceptedOne = page.waitForResponse(r => r.url() === revisionUrl && r.status() === 202);
  await submit.click();
  const one = await (await acceptedOne).json();
  if (!submissions[0].key || submissions[0].key !== submissions[1].key) throw Error('原请求重试没有稳定幂等键');
  await page.goto('about:blank');
  const afterOne = await completed();
  if (afterOne.slots[0].currentVersionId !== before.slots[0].currentVersionId) throw Error('修改了非目标位置');
  if (afterOne.slots[1].versions.length !== 2) throw Error('单张返工未保存版本');
  if (afterOne.rounds.at(-1).id !== one.roundId) throw Error('返工回执与轮次不匹配');
  await open();
  await cards.nth(1).locator('.el-select').click();
  await page.getByRole('option', { name: 'v1 · 历史版本', exact: true }).click();
  await cards.nth(1).getByText('正在查看历史版本，不改变当前结果。', { exact: true }).waitFor();
  await page.waitForFunction(() => {
    const image = document.querySelectorAll('.hx-result-grid .el-image img')[1];
    return image && image.complete && image.naturalWidth > 0;
  });
  const oldUrl = await cards.nth(1).locator('.el-image img').getAttribute('src');
  if (!oldUrl.includes(before.slots[1].versions[0].fileId)) throw Error('历史选择未加载旧文件');
  // Accept on the real API, then lose the response. Confirmation must replay the same request.
  let lostReceipt;
  await page.route(revisionUrl, async route => {
    const response = await route.fetch();
    if (response.status() !== 202) throw Error(await response.text());
    lostReceipt = await response.json();
    await route.abort('failed');
  }, { times: 1 });
  await drawer.getByRole('button', { name: '整套修改', exact: true }).click();
  const wholeNote = '整套统一字号，并保留历史';
  await feedback.fill(wholeNote);
  await submit.click();
  const confirm = page.getByRole('button', { name: '确认上次提交（保留当前意见）', exact: true });
  await confirm.waitFor();
  if (await feedback.inputValue() !== wholeNote) throw Error('未知响应丢失意见');
  const replayed = page.waitForResponse(r => r.url() === revisionUrl && r.status() === 202);
  await confirm.click();
  const replayReceipt = await (await replayed).json();
  if (!lostReceipt || replayReceipt.roundId !== lostReceipt.roundId) throw Error('未知受理重放创建新轮次');
  const [lost, replay] = submissions.slice(-2);
  if (!lost.key || lost.key !== replay.key || JSON.stringify(lost.body) !== JSON.stringify(replay.body)) {
    throw Error('未知受理重放未冻结原键和意见');
  }
  await page.goto('about:blank');
  const final = await completed();
  if (final.rounds.length !== 3 || final.rounds.at(-1).note !== wholeNote) throw Error('整套历史不正确');
  if (final.slots.map(s => s.versions.length).join(',') !== '2,3') throw Error('整套版本不正确');
  await open();
  await drawer.getByText('执行与修改记录（3）', { exact: true }).click();
  await drawer.getByText(singleNote, { exact: true }).waitFor();
  await drawer.getByText(wholeNote, { exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/phase10-revisions.png', fullPage: true });
  if (errors.length) throw Error(errors.join('\n'));
  return 'PHASE10 BROWSER PASS: real single/whole revisions, 409 draft retained, stable key, unknown accepted response replay, background completion, readable historical image, feedback history; pageerrors=0';
}
