// Local built-artifact verification; all API responses are in-memory fixtures.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { resolve, extname, sep } from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = resolve(process.env.RELEASE_BUILD_ROOT || '.')
const server = createServer(async (request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname
  const scope = pathname.match(/^\/(domestic|overseas|shared)(?:\/|$)/)?.[1] || 'shared'
  const directory = resolve(root, `dist-release-${scope}`)
  const relative = pathname.replace(/^\/(domestic|overseas|shared)\/?/, '')
  const file = resolve(directory, relative && pathname !== '/' ? relative : 'index.html')
  if (!file.startsWith(directory + sep)) { response.writeHead(403).end(); return }
  try {
    const bytes = await readFile(file)
    const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }
    response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' }).end(bytes)
  } catch { response.writeHead(404).end() }
})
// Port 0 lets the OS reserve a free local port; no existing service is replaced.
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const base = `http://127.0.0.1:${server.address().port}`
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
let authenticated = true, domesticValid = true, overseasValid = true, overseasDenied = false, configFailure = 0
const domestic = { id: 'fixture-domestic', name: '隔离成员', status: 'active', role: 'designer', identitySessionId: 'fixture-session' }
const overseas = { id: 'fixture-overseas', name: '隔离成员', status: 'active', roles: ['designer'], capabilities: [], identitySessionId: 'fixture-session' }
const errors = [], requests = [], documents = []
await context.route('**/api/**', async route => {
  const path = new URL(route.request().url()).pathname
  requests.push(path)
  const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
  if (path === '/api/identity/v1/config') return configFailure ? json({}, configFailure) : json({ configured: true, corpId: 'fixture', clientId: 'fixture' })
  if (path.endsWith('/logout')) { authenticated = false; return route.fulfill({ status: 204 }) }
  if (!authenticated) return json({}, 401)
  if (path === '/api/identity/v1/me') return json({ name: '隔离成员', sessionId: 'fixture-session' })
  if (path === '/api/identity/v1/tickets') return json({ ticket: 'fixture-ticket' })
  const member = path.startsWith('/api/overseas/') ? overseas : domestic
  if (path.endsWith('/auth/identity/access')) return json({ state: 'allowed', member })
  if (path.endsWith('/auth/identity/session')) return json(member)
  if (path.endsWith('/auth/me') && member === overseas && overseasDenied) return json({}, 403)
  if (path.endsWith('/auth/me')) return json(member, (member === domestic ? domesticValid : overseasValid) ? 200 : 401)
  // Workspaces may show their existing error state; no business data is created.
  return json({ message: '隔离接口未提供业务数据' }, 503)
})
const page = await context.newPage()
page.setDefaultTimeout(20000)
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => { if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents.push(request.url()) })
const button = name => page.getByRole('button', { name, exact: true })
const enter = async business => { await button(`${business}业务`).waitFor(); await button(`${business}业务`).click() }
const reset = () => { authenticated = true; domesticValid = true; overseasValid = true; overseasDenied = false; configFailure = 0 }
try {
  await page.goto(`${base}/?source=legacy#/auth/callback?auth=provider_error&state=%2F`)
  await button('海外业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  assert.equal(new URL(page.url()).search, '?source=legacy')
  assert.equal(new URL(page.url()).hash, '#/auth/callback?auth=provider_error&state=%2F')
  await enter('海外')
  await button('切换业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/overseas/')
  await button('切换业务').click()
  await enter('国内')
  await button('切换业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/domestic/')
  await button('切换业务').click()
  await enter('海外')
  await button('退出登录').click()
  await button('钉钉登录').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  assert.ok(requests.includes('/api/v1/auth/logout') && requests.includes('/api/overseas/v1/auth/logout'))
  console.log('PASS legacy callback query/hash; shared → overseas → domestic → overseas; unified logout')

  reset()
  await page.goto(`${base}/?source=legacy#/api-image-edits/records?record=fixture`)
  await button('切换业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/domestic/')
  assert.equal(new URL(page.url()).search, '?source=legacy')
  assert.equal(new URL(page.url()).hash, '#/api-image-edits/records?record=fixture')
  await button('退出登录').click()
  await button('钉钉登录').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  console.log('PASS legacy domestic deep link and domestic logout')

  reset(); domesticValid = false
  const before = documents.length
  await page.goto(`${base}/domestic/#/api-image-edits/create`)
  await button('海外业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  assert.ok(documents.length - before <= 2, 'invalid domestic session must not loop')
  console.log('PASS domestic expired session redirects once to shared identity')

  reset()
  await page.goto(`${base}/?source=legacy#/overseas/admin/users?tab=fixture`)
  await button('切换业务').waitFor()
  assert.equal(new URL(page.url()).hash, '#/overseas/admin/users?tab=fixture')
  assert.equal(new URL(page.url()).search, '?source=legacy')
  authenticated = false
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await button('钉钉登录').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  console.log('PASS overseas deep link and active-page identity invalidation')

  reset()
  await page.goto(`${base}/overseas/#/overseas/tasks`)
  await button('切换业务').waitFor()
  overseasDenied = true
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await button('海外业务').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  console.log('PASS active overseas permission revocation returns to shared business selection')

  reset(); configFailure = 503
  await page.goto(`${base}/shared/?case=connection-failure#/auth/business`)
  await page.getByRole('alert').waitFor()
  configFailure = 0
  await button('重新连接').click()
  await button('海外业务').waitFor()
  assert.deepEqual(errors, [])
  assert.ok(requests.every(path => path.startsWith('/api/')), 'API URLs remain origin absolute')
  console.log('PASS shared connection failure/retry, no page errors; all APIs remain /api')
  configFailure = 404
  const beforeMissingIdentity = documents.length
  await page.goto(`${base}/shared/#/auth/business`)
  await page.getByRole('alert').waitFor()
  assert.equal(new URL(page.url()).pathname, '/shared/')
  assert.equal(documents.length - beforeMissingIdentity, 1)
  console.log('PASS missing shared identity service stays retryable, no domestic/shared loop')
} finally {
  await context.close()
  await browser.close()
  await new Promise(resolve => server.close(resolve))
}
