import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createFeedbackApi, feedbackError, screenshotIssue } from '../src/api/overseas/feedback'
import { createMembersApi } from '../src/api/overseas/members'
import { IdentityError } from '../src/api/identity/request'

const base = '/api/overseas/v1/feedback'
const row = {
  id: 'sample', question: '保存失败', source: 'AI 设计工作台', task_name: '灯具', sku: 'EX-1',
  submitter_id: 'actor', submitter_name: '设计师', status: 'pending', public_reply: '',
  screenshot_url: base + '/sample/screenshot', version: 1, created_at: '2026-11-19T12:00:00Z', updated_at: '2026-11-19T12:00:00Z'
}
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
const allow = async () => {}

test('反馈上传使用当前海外身份和单张附件，提交人、时间和版本由服务端确定', async () => {
  const screenshot = new File(['png'], '问题.png', { type: 'image/png' })
  const api = createFeedbackApi(async (url, options) => {
    assert.equal(url, base); assert.equal(options?.method, 'POST'); assert.equal(options?.credentials, 'include')
    assert.equal(new Headers(options?.headers).get('X-HX-Request'), '1')
    const body = options?.body
    assert.ok(body instanceof FormData)
    assert.deepEqual([...body.keys()], ['source', 'question', 'task_name', 'sku', 'screenshot'])
    assert.equal(body.get('question'), row.question); assert.equal(body.get('task_name'), row.task_name)
    assert.equal(body.get('screenshot'), screenshot)
    return json(row)
  }, async admin => { assert.equal(admin, false) })
  assert.deepEqual(await api.create({ source: row.source, taskName: row.task_name, sku: row.sku }, ' 保存失败 ', screenshot), row)
  assert.ok(screenshotIssue(new File([], '空.png', { type: 'image/png' })))
  assert.ok(screenshotIssue(new File(['x'], '矢量.svg', { type: 'image/svg+xml' })))
})

test('本人反馈使用受保护的分页，拒绝内部备注或其他地址的截图响应', async () => {
  const mine = (item: unknown) => createFeedbackApi(async (url, options) => {
    assert.equal(url, base + '/mine?offset=20&limit=20'); assert.equal(options?.cache, 'no-store')
    return json({ items: [item], total: 21 })
  }, allow).mine(20, 20)
  assert.equal((await mine(row)).items.length, 1)
  await assert.rejects(mine({ ...row, internal_note: '内部备注' }), /格式错误/)
  await assert.rejects(mine({ ...row, screenshot_url: 'https://example.com/image' }), /格式错误/)
})

test('管理状态筛选、全局状态计数、截图、乐观版本及冲突提示独立于个人读取', async () => {
  const record = { ...row, internal_note: '复核' }
  const change = { version: 1, status: 'resolved' as const, internal_note: '复核', public_reply: '已处理' }
  const api = createFeedbackApi(async (url, options) => {
    assert.equal(options?.credentials, 'include')
    if (String(url).endsWith('/screenshot')) return new Response('image', { headers: { 'Content-Type': 'image/png' } })
    if (String(url).endsWith('feedback?status=processing&offset=0&limit=20')) return json({ items: [], total: 0, counts: { pending: 1, processing: 0, resolved: 0 } })
    assert.equal(url, '/api/overseas/v1/management/feedback/sample')
    if (options?.method === 'PATCH') { assert.deepEqual(JSON.parse(String(options.body)), change); return json({}, 409) }
    return json(record)
  }, async management => { assert.ok(management) })
  assert.equal((await api.list('processing', 0, 20)).counts.pending, 1)
  assert.equal((await api.detail(row.id)).internal_note, '复核')
  assert.equal((await api.screenshot(row.id, true)).type, 'image/png')
  await assert.rejects(api.save(row.id, change), reason => reason instanceof IdentityError && reason.status === 409 && feedbackError(reason).includes('刷新'))
})

test('当前身份核验失败时不发送反馈或管理写入', async () => {
  let calls = 0
  const api = createFeedbackApi(async () => { calls++; return json(row) }, async () => { throw new IdentityError(401, '身份已变化') })
  await assert.rejects(api.create({ source: '关于我们' }, '无法查看'), /身份已变化/)
  await assert.rejects(api.save(row.id, { version: 1, status: 'pending', public_reply: '', internal_note: '' }), /身份已变化/)
  assert.equal(calls, 0)
})

test('成员管理保存和撤销显式反馈授权', async () => {
  for (const flag of [true, false]) {
    const member = { id: 'manager', name: '主管', department: '', roles: ['design_manager' as const], status: 'active' as const, version: 2, createdAt: '', updatedAt: '', feedbackManage: flag }
    const api = createMembersApi(async (_url, options) => { assert.equal(JSON.parse(String(options?.body)).feedbackManage, flag); return json(member) })
    assert.equal((await api.save(member)).feedbackManage, flag)
  }
})
