import test from 'node:test'
import assert from 'node:assert/strict'
import { createIdentityApi } from '../src/api/identity/auth'
import { createApplicationsApi, isApplicationPage } from '../src/api/identity/applications'
import { createMembersApi } from '../src/api/overseas/members'
import { createHttpManagement } from '../src/api/management'
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
const application = { id: 'a/1', name: '成员', status: 'pending', version: 2, createdAt: '2026-10-13', updatedAt: '2026-10-13', reason: null }
test('选定业务session及申请撤回分别使用用途票据，不发送前端身份角色', async () => {
  const calls: { path: string; body: unknown }[] = []
  const api = createIdentityApi(async (url, options) => {
    const path = String(url), body = JSON.parse(String(options?.body)); calls.push({ path, body })
    if (path.endsWith('/tickets')) return json({ ticket: body.purpose + ':' + body.business })
    if (path.endsWith('/session')) return json({ id: 'one', name: '成员', status: 'active', role: 'designer', identitySessionId: 'same' })
    return json({ ...application, status: path.endsWith('/withdraw') ? 'withdrawn' : 'pending' })
  })
  await api.session('domestic', 'same'); await api.apply('overseas', 'same'); await api.withdraw('overseas', 'same')
  assert.deepEqual(calls.map(c => c.path), ['/api/identity/v1/tickets', '/api/v1/auth/identity/session', '/api/identity/v1/tickets', '/api/overseas/v1/auth/identity/application', '/api/identity/v1/tickets', '/api/overseas/v1/auth/identity/application/withdraw'])
  assert.deepEqual(calls.map(c => c.body), [{ business: 'domestic', purpose: 'session', expectedSessionId: 'same' }, { ticket: 'session:domestic' }, { business: 'overseas', purpose: 'application', expectedSessionId: 'same' }, { ticket: 'application:overseas' }, { business: 'overseas', purpose: 'application', expectedSessionId: 'same' }, { ticket: 'application:overseas' }])
})
test('确认后跨标签换号导致票据401，不得请求另一身份的申请或会话', async () => {
  for (const action of ['apply', 'withdraw', 'session', 'access'] as const) {
    const calls: string[] = []
    const api = createIdentityApi(async (url, options) => {
      calls.push(String(url)); assert.equal(JSON.parse(String(options?.body)).expectedSessionId, 'confirmed-identity')
      return new Response(JSON.stringify({ detail: '身份已变化' }), { status: 401 })
    })
    await assert.rejects(api[action]('overseas', 'confirmed-identity'), { status: 401 })
    assert.deepEqual(calls, ['/api/identity/v1/tickets'])
  }
})
test('双边申请分页、审批版本与保护头准确发送，畸形页不伪造成功', async () => {
  for (const business of ['domestic', 'overseas'] as const) {
    const base = business === 'domestic' ? '/api/v1/management/users/applications' : '/api/overseas/v1/members/applications'
    const api = createApplicationsApi(business, async (url, options) => {
      if (options?.method === 'GET') { assert.equal(String(url), `${base}?page=2&pageSize=20&status=pending&search=%E5%90%8C%E5%90%8D`); return json({ items: [application], total: 21, page: 2, pageSize: 20 }) }
      assert.equal(String(url), `${base}/a%2F1/decision`)
      assert.equal((options?.headers as Record<string, string>)['X-HX-Request'], '1')
      assert.deepEqual(JSON.parse(String(options?.body)), { decision: 'reject', reason: '请核对业务', version: 2 })
      return json({ ...application, status: 'rejected', version: 3 })
    })
    assert.equal((await api.listApplications({ page: 2, pageSize: 20, status: 'pending', search: '同名' })).total, 21)
    assert.equal((await api.decideApplication('a/1', { decision: 'reject', reason: '请核对业务', version: 2 })).version, 3)
  }
  assert.equal(isApplicationPage({ items: [application], total: -1, page: 1, pageSize: 20 }), false)
  assert.equal(isApplicationPage({ items: [{ ...application, version: 0 }], total: 1, page: 1, pageSize: 20 }), false)
})
test('正式和历史目录query由服务端计数；国内审批沿用国内请求生命周期', async () => {
  const paths: string[] = []
  const fetcher: typeof fetch = async (url, options) => {
    paths.push(String(url))
    if (String(url).includes('/decision')) { assert.equal((options?.headers as Record<string, string>)['X-HX-Request'], '1'); return json({ ...application, status: 'approved' }) }
    return json({ items: [], total: 0, page: 1, pageSize: 20 })
  }
  await createMembersApi(fetcher).list({ search: '', status: '', role: '', page: 1, pageSize: 20, directory: 'legacy' })
  const domestic = createHttpManagement('/api/v1', fetcher)
  await domestic.listUsers({ page: 1, pageSize: 20, directory: 'members' })
  await domestic.decideApplication('a/1', { decision: 'approve', role: 'designer', version: 2 })
  assert.deepEqual(paths, ['/api/overseas/v1/members?page=1&pageSize=20&directory=legacy', '/api/v1/management/users?page=1&pageSize=20&directory=members', '/api/v1/management/users/applications/a%2F1/decision'])
})
