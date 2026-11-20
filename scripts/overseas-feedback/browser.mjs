import assert from 'node:assert/strict'
import { verifyTaskFeedback } from './task-context.mjs'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.FEEDBACK_UI_URL || 'http://127.0.0.1:4189/'
const picture = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGNkaGBgYGBgAhEMDAAGKgCE2O/yUgAAAABJRU5ErkJggg==', 'base64')
const browser = await chromium.launch()
const records = []
let conflict = true, pictureViews = 0

async function actor(id, canManage, viewport = { width: 1280, height: 800 }) {
  const context = await browser.newContext({ viewport })
  const member = { id, name: id, identitySessionId: id, status: 'active', roles: [canManage ? 'design_manager' : 'designer'],
    capabilities: canManage ? ['task.read', 'feedback.manage'] : ['task.read'] }
  await context.route('**/*', async route => {
    const path = new URL(route.request().url())
    if (path.origin !== new URL(base).origin) return route.abort()
    if (!path.pathname.startsWith('/api/')) return route.continue()
    const json = (data, status = 200) => route.fulfill({ json: data, status })
    const endpoint = path.pathname
    if (endpoint === '/api/identity/v1/config') return json({ configured: true, corpId: 'local', clientId: 'local' })
    if (endpoint === '/api/identity/v1/me') return json({ name: id, sessionId: id })
    if (endpoint.endsWith('/tickets')) return json({ ticket: 'local' })
    if (endpoint.endsWith('/auth/identity/access')) return json(endpoint.includes('/overseas/') ? { state: 'allowed', member } : { state: 'unregistered' })
    if (endpoint.endsWith('/auth/me')) return json(member)
    const personal = ({ internal_note, ...item }) => item
    if (endpoint === '/api/overseas/v1/feedback' && route.request().method() === 'POST') {
      const body = route.request().postDataBuffer()
      assert.ok(body.includes(Buffer.from('关于我们')) && body.includes(picture))
      const record = { id: 'feedback-1', question: '页面打不开', source: '关于我们', task_name: null, sku: null, submitter_id: id, submitter_name: id,
        status: 'pending', public_reply: '', internal_note: '', screenshot_url: '/api/overseas/v1/feedback/feedback-1/screenshot',
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(), version: 1 }
      records.push(record)
      return json(personal(record), 201)
    }
    if (endpoint.endsWith('/feedback/mine')) {
      const items = records.filter(r => r.submitter_id === id).map(personal)
      return json({ items, total: items.length })
    }
    if (endpoint.includes('/management/feedback')) {
      if (!canManage) return json({}, 403)
      if (endpoint.endsWith('/feedback')) {
        const counts = { pending: 0, processing: 0, resolved: 0 }
        for (const record of records) counts[record.status]++
        const items = records.filter(r => !path.searchParams.has('status') || r.status === path.searchParams.get('status'))
        return json({ items, total: items.length, counts })
      }
      const row = records[0]
      if (route.request().method() === 'PATCH') {
        if (conflict) {
          conflict = false; row.version++; row.internal_note = '并发更新'
          return json({}, 409)
        }
        const edit = route.request().postDataJSON()
        assert.equal(edit.version, row.version)
        Object.assign(row, edit, { version: row.version + 1 })
      }
      return json(row)
    }
    if (endpoint.endsWith('/screenshot')) {
      if (!canManage && records[0].submitter_id !== id) return json({}, 403)
      pictureViews++
      return route.fulfill({ contentType: 'image/png', body: picture })
    }
    return json({}, 404)
  })
  const page = await context.newPage()
  page.on('pageerror', error => console.error(error.message))
  page.setDefaultTimeout(30000)
  await page.goto(new URL('#/overseas/about', base).href, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: '公司介绍' }).waitFor()
  return page
}
try {
  const user = await actor('设计师', false)
  await user.getByRole('button', { name: '意见反馈' }).click()
  await user.getByRole('button', { name: '提交反馈' }).click()
  await user.getByText('请填写问题描述').waitFor()
  await user.getByRole('textbox', { name: '问题描述' }).fill('页面打不开')
  await user.getByLabel('添加截图').setInputFiles({ name: '页面.png', mimeType: 'image/png', buffer: picture })
  await user.getByAltText('已选问题截图').waitFor()
  await user.getByRole('button', { name: '提交反馈' }).click()
  await user.getByText('暂无管理员回复').waitFor()
  await user.getByRole('button', { name: '关闭', exact: true }).last().click()

  const manager = await actor('主管', true)
  await manager.goto(new URL('#/overseas/admin/feedback', base).href)
  await manager.getByRole('button', { name: '查看处理' }).click()
  await manager.getByAltText('用户提交的问题截图').waitFor()
  assert.equal(pictureViews, 1)
  await manager.getByRole('radiogroup', { name: '处理状态', exact: true }).getByText('已处理', { exact: true }).click()
  await manager.getByRole('button', { name: '保存处理' }).click()
  await manager.getByText('请填写给提交人的处理结果').waitFor()
  await manager.getByRole('textbox', { name: '回复提交人' }).fill('初次编辑')
  await manager.getByRole('button', { name: '保存处理' }).click()
  await manager.getByText(/这条反馈已由其他管理员更新/).waitFor()
  await manager.getByRole('button', { name: '刷新最新记录' }).click()
  await manager.waitForFunction(() => document.querySelector('[aria-label="内部备注"]').value === '并发更新')
  await manager.getByRole('radiogroup', { name: '处理状态', exact: true }).getByText('已处理', { exact: true }).click()
  await manager.getByRole('textbox', { name: '回复提交人' }).fill('已修复')
  await manager.getByRole('textbox', { name: '内部备注' }).fill('排查记录')
  await manager.getByRole('button', { name: '保存处理' }).click()
  await manager.getByRole('button', { name: '查看详情' }).waitFor()

  await user.goto(new URL('#/overseas/about?feedback=mine', base).href)
  await user.getByText('已修复', { exact: true }).waitFor()
  assert.equal(await user.getByText('排查记录').count(), 0)
  const other = await actor('其他设计师', false, { width: 390, height: 844 })
  await other.goto(new URL('#/overseas/about?feedback=mine', base).href)
  await other.getByText('你还没有提交过反馈').waitFor()
  const close = other.getByRole('button', { name: '关闭', exact: true }).last()
  await close.click({ trial: true })
  const footer = await close.boundingBox()
  assert.ok(footer && footer.x >= 0 && footer.x + footer.width <= 390 && footer.y + footer.height <= 844, JSON.stringify(footer))
  assert.equal(await other.getByText('页面打不开').count(), 0)
  await other.goto(new URL('#/overseas/admin/feedback', base).href)
  await other.getByText('暂无反馈管理权限').waitFor()
  await verifyTaskFeedback(user, base, picture)
  console.log('PASS 反馈提交与截图、权限、处理校验、冲突刷新、公开回复、内部备注隔离、390px 抽屉')
} finally { await browser.close() }
