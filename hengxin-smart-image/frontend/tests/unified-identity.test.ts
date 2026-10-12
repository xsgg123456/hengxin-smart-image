import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createIdentityApi, IdentityError } from '../src/api/identity/auth'
import { mayEnter } from '../src/api/identity/access'
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
for (const [domestic, overseas] of [[true, true], [false, true], [true, false], [false, false]]) {
  test(`真实API合同四权限组合 ${domestic}/${overseas}：两张票据分别兑换`, async () => {
    const tickets = new Map<string, string>()
    const api = createIdentityApi(async (url, options) => {
      assert.equal(options?.credentials, 'include')
      assert.equal((options?.headers as Record<string, string>)['X-HX-Request'], '1')
      const body = JSON.parse(String(options?.body))
      if (String(url).endsWith('/tickets')) { tickets.set(body.business, `${body.business}-ticket`); return json({ ticket: `${body.business}-ticket` }) }
      const business = String(url).includes('/overseas/') ? 'overseas' : 'domestic'
      assert.equal(body.ticket, tickets.get(business))
      return (business === 'domestic' ? domestic : overseas) ? json({ id: '1', name: '成员', status: 'active', role: 'operator', roles: ['designer'], capabilities: ['task.read', 'task.design', 'stats.read'] }) : json({}, 403)
    })
    const [a, b] = await Promise.all([api.access('domestic'), api.access('overseas')])
    const identity = { authenticated: true, domestic: a.state === 'allowed', overseas: b.state === 'allowed' }
    assert.equal(mayEnter(identity, 'domestic'), domestic)
    assert.equal(mayEnter(identity, 'overseas'), overseas)
    assert.equal(tickets.size, 2)
  })
}
test('503与网络故障必须可重试，不能显示无权限；401清身份', async () => {
  assert.equal((await createIdentityApi(async () => json({}, 503)).access('overseas')).state, 'error')
  assert.equal((await createIdentityApi(async () => { throw new Error('network') }).access('overseas')).state, 'error')
  await assert.rejects(createIdentityApi(async () => json({}, 401)).access('overseas'), (e: unknown) => e instanceof IdentityError && e.status === 401)
})
test('全局退出必须先撤销统一身份，失败不调用业务退出', async () => {
  const calls: string[] = []
  const api = createIdentityApi(async url => { calls.push(String(url)); return json({}, 503) })
  await assert.rejects(api.logout())
  assert.deepEqual(calls, ['/api/identity/v1/logout'])
})
test('全局退出成功后清理两个业务cookie，部分失败不能假装成功', async () => {
  const calls: string[] = []
  const api = createIdentityApi(async url => { calls.push(String(url)); return String(url).includes('overseas') ? json({}, 503) : new Response(null, { status: 204 }) })
  await assert.rejects(api.logout(), /部分业务退出未完成/)
  assert.equal(calls[0], '/api/identity/v1/logout')
  assert.equal(calls.length, 3)
})
test('海外成员响应必须含真实非空角色且启用', async () => {
  const api = createIdentityApi(async url => String(url).endsWith('/tickets') ? json({ ticket: 'ticket' }) : json({ id: '1', name: '成员', status: 'active', roles: [] }))
  assert.equal((await api.access('overseas')).state, 'error')
})
