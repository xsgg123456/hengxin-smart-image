// Disposable browser context; all API calls intercepted, no production writes.
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext(), page = await context.newPage(), calls = [], errors = []
page.setDefaultTimeout(15000)
page.on('pageerror', error => errors.push(error.message))
let config = { version: 1, capacity: 10, timeoutCapacity: 7200, concurrency: 1, timeoutSeconds: 600, maxUploadBytes: 10485760, dingtalk: { corpId: '', appId: '', callbackDomain: '', state: 'unconfigured' }, audit: [] }
await context.route('**/*', async route => {
  const req = route.request(), u = new URL(req.url()), p = u.pathname
  if (u.origin !== new URL(base).origin) return route.abort()
  if (!p.startsWith('/api/')) return route.continue()
  calls.push(p)
  let body
  if (p.endsWith('/auth/me')) body = { id: 'test', name: '隔离超管', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/management/settings')) {
    if (req.method() === 'PUT') {
      const input = req.postDataJSON()
      assert.equal('defaultSkillIds' in input, false)
      config = { ...config, ...input, dingtalk: config.dingtalk, version: config.version + 1 }
    }
    body = config
  } else if (p.endsWith('/management/execution-settings')) body = {
    api: { enabled: true, taskConcurrency: 5, imagesPerBatch: 10, requestTimeoutSeconds: 180, downloadTimeoutSeconds: 60, leaseSeconds: 360, model: 'test', quality: 'xhigh', resolution: '1K', imagesPerRequest: 1, sizePolicy: '跟随原图宽高' },
    cli: { enabled: true, concurrency: config.concurrency, capacity: 10, timeoutSeconds: 600, timeoutCapacity: 7200, model: 'test', reasoningEffort: 'high', usesSkills: false },
    maxUploadBytes: config.maxUploadBytes, retention: { enabled: true, cacheIdleDays: 1, historyIdleDays: 3 }
  }
  else { errors.push(`Unexpected API ${p}`); return route.fulfill({ status: 501, body: '{}' }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
try {
  await page.goto(base + '#/management/settings')
  await page.getByText('CLI 执行与上传 · 配置 v1', { exact: true }).waitFor()
  assert.equal(await page.getByText(/默认 Skill/).count(), 0)
  await page.getByRole('spinbutton', { name: 'CLI 全局执行并发', exact: true }).fill('2')
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await page.getByText('CLI 执行与上传 · 配置 v2', { exact: true }).waitFor()
  assert.equal(config.concurrency, 2)
  assert.ok(calls.every(p => !/skill|\/workspace/.test(p)))
  assert.deepEqual(errors, [])
  console.log('PASS: 系统配置读写及现行执行参数完整，无旧Skill请求/字段/选择项')
} finally { await context.close(); await browser.close() }
