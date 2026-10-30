// No Playwright routing: it disables HTTP cache, invalidating the 304 regression.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { startFixture, imageBytes } from './fixture-server.mjs'
import { cacheScenarios } from './cache-scenarios.mjs'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const output = resolve('output/image-cache')
await mkdir(output, { recursive: true })
const fixture = await startFixture(), { state, origin } = fixture
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
const page = await context.newPage(), checks = [], errors = [], evidence = {}
page.setDefaultTimeout(20000)
page.on('pageerror', error => errors.push(error.message))
const originalRequests = () => state.requests.filter(r => !r.small)
const settle = () => page.waitForFunction(() => { const s = window.imageTest.cache.stats(); return s.active === 0 && s.queued === 0 })
const viewer = () => page.locator('.el-image-viewer__wrapper')
const shownImage = () => page.locator('.el-image-viewer__img:visible')
const originalVisible = () => page.waitForFunction(() => [...document.querySelectorAll('.el-image-viewer__img')].some(img => getComputedStyle(img).display !== 'none' && img.naturalWidth === 1600 && img.naturalHeight === 1000))
const screenshot = name => page.screenshot({ path: resolve(output, name + '.png'), animations: 'disabled' })
try {
  state.thumbnailFailures.set('a', 1)
  await page.goto(origin)
  await page.waitForFunction(() => window.imageTest && [...document.querySelectorAll('.gallery img')].length === 3 && [...document.querySelectorAll('.gallery img')].every(img => img.naturalWidth === 240 && img.naturalHeight === 150))
  assert.deepEqual(state.requests.filter(r => r.id === 'a' && r.small).map(r => r.status), [429, 200])
  checks.push('真实HTTP缩略图首次429后组件有限退避自动重试并恢复，无需刷新页面')
  assert.equal(originalRequests().filter(r => r.method === 'GET').length, 0)
  await screenshot('01-thumbnails')
  checks.push('真实组件列表图片GET只读取thumbnail=true，缩略图240×150，未点击不下载原件')

  await page.getByRole('button', { name: '预取当前会话', exact: true }).click()
  await page.waitForFunction(() => window.imageTest.cache.stats().entries === 3)
  await settle()
  const beforeOpen = originalRequests().filter(r => r.method === 'GET').length
  assert.equal(beforeOpen, 3)
  await page.getByRole('button', { name: '预览 a.png', exact: true }).click()
  await originalVisible(); await settle()
  assert.equal(originalRequests().filter(r => r.method === 'GET').length, beforeOpen)
  assert(originalRequests().some(r => r.id === 'a' && r.method === 'HEAD' && r.status === 304))
  await screenshot('02-original-preview')
  checks.push('整批原图预取后点击只HEAD校验，不二次GET，预览自然尺寸1600×1000')

  await page.keyboard.press('ArrowRight'); await originalVisible(); await settle()
  await viewer().getByText('b.png', { exact: false }).waitFor()
  const transformBefore = await shownImage().evaluate(img => img.style.transform)
  await shownImage().hover(); await page.mouse.wheel(0, -180)
  await page.waitForFunction(before => [...document.querySelectorAll('.el-image-viewer__img')].some(img => getComputedStyle(img).display !== 'none' && img.style.transform !== before), transformBefore)
  assert.notEqual(await shownImage().evaluate(img => img.style.transform), transformBefore)
  assert.equal(await shownImage().evaluate(img => img.naturalWidth), 1600)
  const downloadPromise = page.waitForEvent('download')
  await viewer().getByRole('button', { name: '下载原图', exact: true }).click()
  const download = await downloadPromise
  await download.saveAs(resolve(output, 'download-original.png'))
  const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
  evidence.download = { filename: download.suggestedFilename(), sha256: sha256(await readFile(resolve(output, 'download-original.png'))), expected: sha256(imageBytes('b')) }
  assert.equal(evidence.download.sha256, evidence.download.expected)
  await screenshot('03-zoom-download')
  await page.keyboard.press('ArrowLeft'); await originalVisible(); await settle()
  await page.keyboard.press('Escape'); await viewer().waitFor({ state: 'hidden' })
  const repeatedGetCount = originalRequests().filter(r => r.method === 'GET').length
  await page.getByRole('button', { name: '预览 a.png', exact: true }).press('Enter')
  await originalVisible(); await settle()
  assert.equal(originalRequests().filter(r => r.method === 'GET').length, repeatedGetCount)
  checks.push('左右键、Enter重开、滚轮缩放保持1600原件；下载字节SHA256与fixture原件完全一致')
  await page.keyboard.press('Escape'); await viewer().waitFor({ state: 'hidden' })

  const reloadStart = state.requests.length
  await page.reload(); await page.waitForFunction(() => !!window.imageTest)
  await page.getByRole('button', { name: '预取当前会话', exact: true }).click()
  await page.waitForFunction(() => window.imageTest.cache.stats().entries === 3); await settle()
  const reloaded = state.requests.slice(reloadStart)
  const reloadedOriginals = reloaded.filter(r => r.method === 'GET' && !r.small)
  assert.equal(reloadedOriginals.length, 3)
  assert(reloadedOriginals.every(r => r.status === 304 && r.bytes === 0 && r.ifNoneMatch))
  evidence.refresh = reloaded
  checks.push('刷新清空JS内存后，真实Chromium HTTP缓存原件GET全部304且零body字节')

  state.status.set('a', 403)
  await page.getByRole('button', { name: '预览 a.png', exact: true }).click()
  await viewer().getByRole('alert').waitFor()
  assert.equal(await page.locator('.el-image-viewer__img[src^="blob:"]:visible').count(), 0)
  await screenshot('04-denied')
  state.status.delete('a')
  await viewer().getByRole('button', { name: '重新加载', exact: true }).click()
  await originalVisible(); await settle()
  await screenshot('05-retry-recovered')
  checks.push('真实预览403时不显示旧缓存原图；错误提示与重新加载按钮可恢复原图')
  await page.keyboard.press('Escape'); await viewer().waitFor({ state: 'hidden' })
  for (const id of ['attachment', 'material']) {
    await page.getByRole('button', { name: `预览 ${id}.png`, exact: true }).click()
    await originalVisible(); await settle()
    const requests = state.requests.filter(r => r.id === id)
    assert(requests.some(r => r.small && r.url.endsWith('?preview=true&thumbnail=true')))
    assert(requests.some(r => !r.small && r.method === 'GET' && r.url.endsWith('?preview=true')))
    await page.keyboard.press('Escape'); await viewer().waitFor({ state: 'hidden' })
  }
  checks.push('图片附件与任务素材共同组件分别使用preview=true&thumbnail=true和原件preview=true链路')
  evidence.componentRequests = [...state.requests]

  await cacheScenarios(page, state, checks)
  await page.getByRole('button', { name: '退出账号', exact: true }).click()
  assert.equal(await page.locator('.gallery').count(), 0)
  await screenshot('06-logged-out')
  assert.deepEqual(state.unexpected, [])
  assert.deepEqual(errors, [])
  const result = { passed: true, scope: '隔离localhost HTTP fixture + 生产Vue组件/缓存 + Chromium；不代表生产延迟或真实后端鉴权验收', checks, errors, evidence, finalRequests: state.requests }
  await writeFile(resolve(output, 'result.json'), JSON.stringify(result, null, 2))
  await Promise.all(['failure.json', 'failure.png'].map(name => rm(resolve(output, name), { force: true })))
  console.log(JSON.stringify({ passed: true, checks, screenshots: output }, null, 2))
} catch (error) {
  await screenshot('failure').catch(() => {})
  await writeFile(resolve(output, 'failure.json'), JSON.stringify({ error: String(error), stack: error.stack, checks, errors, requests: state.requests }, null, 2))
  throw error
} finally { await context.close(); await browser.close(); await fixture.close() }
