import assert from 'node:assert/strict'

export async function verifyTaskFeedback(page, base, picture) {
  const gates = new Map()
  const submitted = []
  function delay(kind) {
    let release, started
    const pending = new Promise(resolve => { release = resolve })
    const arrived = new Promise(resolve => { started = resolve })
    gates.set(kind, { pending, started })
    return { arrived, release }
  }
  async function gate(kind) {
    const entry = gates.get(kind)
    if (!entry) return
    gates.delete(kind)
    entry.started()
    return entry.pending
  }
  const task = id => ({ id, name: '任务 ' + id, remarks: '', platform: 'Amazon', market: '', productName: '灯', brand: '',
    skus: [{ code: 'SKU-01' }, { code: 'SKU-02' }], createdBy: { id: 'designer', name: '设计师' },
    designer: { id: 'designer', name: '设计师', status: 'active', eligible: true }, events: [], capabilities: [], version: 1,
    createdAt: '2026-11-18T00:00:00Z', updatedAt: '2026-11-18T00:00:00Z', status: id === 'C' ? 'studio' : 'pending_review', workflow: 'studio' })
  await page.route('**/api/overseas/v1/tasks/**', async route => {
    const id = new URL(route.request().url()).pathname.split('/').pop()
    if (id === 'materials') return route.fulfill({ json: [] })
    const status = await gate(id) || 200
    return route.fulfill({ status, json: status === 200 ? task(id) : {} })
  })
  await page.route('**/api/overseas/v1/feedback', async route => {
    const request = route.request()
    const form = await new Response(request.postDataBuffer(), { headers: request.headers() }).formData()
    const item = Object.fromEntries(form)
    submitted.push(item)
    await gate('POST')
    return route.fulfill({ status: 201, json: { id: 'entry', question: item.question, source: item.source,
      task_name: item.task_name || null, sku: item.sku || null, submitter_id: 'designer', submitter_name: '设计师',
      public_reply: '', status: 'pending', screenshot_url: null, version: 1, created_at: '2026-11-19', updated_at: '2026-11-19' } })
  })
  const navigate = path => page.goto(new URL('#/overseas/' + path, base).href)
  const open = () => page.getByRole('button', { name: '意见反馈' }).click()
  const question = page.getByRole('textbox', { name: '问题描述' })
  const send = page.getByRole('button', { name: '提交反馈', exact: true })
  const loading = page.getByText('正在读取任务信息…')
  const attach = () => page.getByLabel('添加截图').setInputFiles({ name: '草稿.png', mimeType: 'image/png', buffer: picture })
  const hasContext = (id, label = '任务详情') => page.locator('.support-source').filter({ hasText: label + ' · 任务 ' + id + ' · SKU-01、SKU-02' }).waitFor()

  const first = delay('A')
  await navigate('tasks/A')
  await first.arrived
  await open()
  await question.fill('等候时填写的描述')
  await attach()
  await loading.waitFor()
  assert.ok(await send.isDisabled())
  first.release()
  await hasContext('A')
  assert.equal(await question.inputValue(), '等候时填写的描述')
  await page.getByAltText('已选问题截图').waitFor()

  await page.getByRole('button', { name: '取消', exact: true }).click()
  const refresh = delay('A')
  await page.getByRole('button', { name: '刷新任务详情' }).click()
  await refresh.arrived
  await open()
  assert.equal(await question.inputValue(), '等候时填写的描述')
  assert.ok(await send.isDisabled())
  refresh.release()
  await hasContext('A')
  await send.click()
  await page.getByRole('tab', { name: '我的反馈', selected: true }).waitFor()
  assert.equal(submitted[0].task_name, '任务 A')
  assert.equal(submitted[0].sku, 'SKU-01、SKU-02')
  assert.equal(submitted[0].screenshot.name, '草稿.png')

  const failed = delay('B')
  await navigate('tasks/B?feedback=mine')
  await failed.arrived
  await page.getByRole('tab', { name: '我的反馈', selected: true }).waitFor()
  await page.getByRole('tab', { name: '提交反馈' }).click()
  assert.equal(await question.inputValue(), '')
  await question.fill('此任务打不开')
  assert.ok(await send.isDisabled())
  failed.release(404)
  await page.locator('.support-source').filter({ hasText: '任务详情 · B' }).waitFor()
  const late = delay('POST')
  await send.click()
  await late.arrived
  assert.equal(submitted[1].source, '任务详情 · B')
  assert.equal(submitted[1].task_name, undefined)
  assert.equal(submitted[1].sku, undefined)

  const nextTask = delay('C')
  await navigate('tasks/C?feedback=mine')
  await nextTask.arrived
  await page.getByRole('tab', { name: '我的反馈', selected: true }).waitFor()
  await page.getByRole('tab', { name: '提交反馈' }).click()
  await question.fill('下一页新草稿')
  late.release()
  nextTask.release()
  await hasContext('C', 'AI 设计工作台')
  assert.equal(await question.inputValue(), '下一页新草稿')
  assert.equal(await page.getByAltText('已选问题截图').count(), 0)
  const oldRead = delay('D')
  await navigate('tasks/D')
  await oldRead.arrived
  await navigate('tasks/E')
  await open()
  await hasContext('E')
  const completedRead = page.waitForResponse(response => response.url().endsWith('/tasks/D'))
  oldRead.release()
  await completedRead
  await hasContext('E')
  assert.equal(await question.inputValue(), '')
  console.log('PASS 反馈任务上下文加载、同任务刷新、失败回退、跨页深链、迟到提交响应和附件草稿隔离')
}
