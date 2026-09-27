// Run against an isolated local Vite server; all API and external calls are intercepted.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { isAbsolute, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { intercept } from './browser-fixtures.mjs'

const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const origin = new URL(process.env.PERFORMANCE_TEST_ORIGIN || 'http://127.0.0.1:3027').origin
assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname), 'local test origin only')
const output = resolve('output/playwright/performance-1a')
await mkdir(output, { recursive: true })
await writeFile(resolve(output, 'evidence.json'), JSON.stringify({ passed: false, status: 'running' }))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 6000 } })
const state = { user: { id: 'user-A', name: '成员A', role: 'operator', status: 'active' },
  disabled: false, authCalls: 0, imageCalls: 0, unexpected: [] }
await intercept(context, origin, state)
const page = await context.newPage()
const errors = []
page.on('pageerror', error => errors.push(error.message))
const checks = []
const wait = async (predicate, message) => {
  const until = Date.now() + 20000
  while (!predicate()) {
    assert(Date.now() < until, message)
    await new Promise(resolve => setTimeout(resolve, 25))
  }
}
const unlock = () => page.waitForFunction(() => document.documentElement.dataset.identityLocked !== 'true')
try {
  let releaseImages
  state.imageBarrier = new Promise(resolve => { releaseImages = resolve })
  await page.goto(origin + '/#/templates/index', { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: '模板库', exact: true }).waitFor()
  await wait(() => state.imageCalls === 44, 'all native image requests must be observed')
  const authBefore = state.authCalls
  releaseImages()
  await page.getByText('图片加载失败', { exact: false }).first().waitFor()
  await wait(() => state.authCalls > authBefore, 'native errors must verify current identity')
  await page.waitForTimeout(250)
  assert.equal(state.authCalls - authBefore, 1, '44 failures must share one identity request')
  await unlock()
  assert(await page.getByRole('heading', { name: '模板库', exact: true }).isVisible())
  checks.push('44 native image failures share one auth check; 404 does not log out')
  await page.screenshot({ path: resolve(output, 'image-errors.png'), fullPage: true })

  let releaseAuth
  const imagesBeforeResume = state.imageCalls
  state.authBarrier = new Promise(resolve => { releaseAuth = resolve })
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))
  })
  assert.equal(await page.evaluate(() => document.documentElement.dataset.identityLocked), 'true')
  assert(!(await page.getByRole('heading', { name: '模板库', exact: true }).isVisible()))
  releaseAuth()
  state.authBarrier = undefined
  await unlock()
  await page.getByRole('heading', { name: '模板库', exact: true }).waitFor()
  await page.waitForTimeout(150)
  assert.equal(state.imageCalls, imagesBeforeResume, 'same-identity resume must not reload every original')
  checks.push('persisted page lifecycle hides protected content until reauthorization')

  for (const oldStatus of [200, 401]) {
    let releaseOld, oldStarted
    state.oldStatus = oldStatus
    state.oldBarrier = new Promise(resolve => { releaseOld = resolve })
    const started = new Promise(resolve => { oldStarted = resolve })
    state.oldStarted = oldStarted
    await page.evaluate(async () => {
      const { createRequest } = await import('/src/api/hengxin/http.ts')
      window.__oldRead = createRequest('/api/v1')('/test-old', value => typeof value === 'object')
        .then(() => 'unexpected-success', error => error.code || error.message)
    })
    await started
    state.user = { ...state.user, id: `user-B-${oldStatus}`, name: `成员B${oldStatus}` }
    await page.evaluate(() => window.dispatchEvent(new Event('hengxin:identity-changed')))
    releaseOld()
    assert.notEqual(await page.evaluate(() => window.__oldRead), 'unexpected-success')
    await unlock()
    await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor()
    assert(!(await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).isVisible()))
  }
  checks.push('old success and 401 cannot fill or log out the new identity')

  state.disabled = true
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })))
  await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).waitFor()
  assert(!(await page.getByRole('heading', { name: '替换壁纸', exact: true }).isVisible()))
  checks.push('disabled identity 403 locks workspace on resume')
  await page.screenshot({ path: resolve(output, 'disabled.png'), fullPage: true })
  state.disabled = false
  await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).click()
  await page.getByRole('heading', { name: '替换壁纸', exact: true }).waitFor()
  const sibling = await context.newPage()
  await sibling.goto(origin + '/#/auth/login', { waitUntil: 'domcontentloaded' })
  await sibling.evaluate(() => localStorage.setItem('hengxin:logout', crypto.randomUUID()))
  await page.getByRole('button', { name: '已有会话，重新连接', exact: true }).waitFor()
  assert(!(await page.getByRole('heading', { name: '替换壁纸', exact: true }).isVisible()))
  await sibling.close()
  checks.push('real cross-tab storage logout removes protected content')
  assert.deepEqual(errors, [])
  assert.deepEqual(state.unexpected, [])
  await writeFile(resolve(output, 'evidence.json'), JSON.stringify({ passed: true, checks, errors,
    authCalls: state.authCalls, imageCalls: state.imageCalls,
    scope: 'Real Vue/browser; local contract fixtures; synthetic persisted lifecycle, not real BFCache certification' }, null, 2))
  console.log(JSON.stringify({ passed: true, checks }, null, 2))
} catch (error) {
  await writeFile(resolve(output, 'evidence.json'), JSON.stringify({ passed: false, checks,
    error: error instanceof Error ? error.message : String(error), errors }, null, 2))
  throw error
} finally {
  await context.close()
  await browser.close()
}
