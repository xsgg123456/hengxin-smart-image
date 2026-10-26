import assert from 'node:assert/strict'
import test from 'node:test'
import { createRenderer, defineComponent, h, nextTick } from 'vue'
import { createCodexAuthApi, isAccount, isAuthorization, officialAuthorizationUrl, type Account, type Authorization, type CodexAuthApi } from '../src/api/codex-auth'
import { useAuthorization } from '../src/views/codex-auth/use-authorization'
import { useAccount } from '../src/views/codex-auth/use-account'
import { managementCapability } from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/request'

const account: Account = { status: 'unchecked', email: 'same@example.test', workspace: 'workspace-1', checked: '', updated: '', audit: [], revision: 2, checking: false }
const authorization: Authorization = { id: 'candidate', step: 'waiting', userCode: 'ABCD-EFGH', verificationUrl: 'https://auth.openai.com/codex/device', expiresAt: Math.floor(Date.now() / 1000) + 180, candidateEmail: '', candidateWorkspace: '', different: false, message: '' }
function fakeApi(overrides: Partial<CodexAuthApi> = {}): CodexAuthApi {
  return { get: async () => ({ ...account }), check: async () => ({ ...account, checking: true }), start: async () => ({ ...authorization }), poll: async () => ({ ...authorization }), retry: async () => ({ ...authorization, step: 'checking' }), activate: async () => ({ ...account, status: 'ready' }), cancel: async () => ({ ok: true }), remove: async () => ({ ...account, status: 'empty' }), ...overrides }
}
const renderer = createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {} })
function mount<T>(setup: () => T) {
  let state!: T
  const app = renderer.createApp(defineComponent({ setup() { state = setup(); return () => h('div') } }))
  app.mount({}); return { state, close: () => app.unmount() }
}
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick() }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
const events = () => ({ close() {}, activate(_account: Account, _different: boolean) {}, failure(_reason: unknown) {} })

for (const side of ['domestic', 'overseas'] as const) test(`${side}: API 路由隔离，所有修改带浏览器校验，删除带版本`, async () => {
  const calls: { url: string; init: RequestInit }[] = []
  const fetcher: typeof fetch = async (url, init) => {
    calls.push({ url: String(url), init: init! })
    const body = String(url).includes('authorizations') ? init?.method === 'DELETE' ? { ok: true } : String(url).endsWith('/activate') ? account : authorization : account
    return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
  }
  const api = createCodexAuthApi(side, fetcher)
  await api.get(); await api.check(); await api.start('replace', 2); await api.poll('a/b'); await api.retry('a/b'); await api.activate('a/b', true); await api.cancel('a/b'); await api.remove(2)
  const prefix = side === 'domestic' ? '/api/v1/management/codex-auth' : '/api/overseas/v1/management/codex-auth'
  assert.ok(calls.every(c => c.url.startsWith(prefix)))
  assert.ok(calls[3].url.endsWith('/a%2Fb'))
  for (const call of calls.filter(c => c.init.method !== 'GET')) assert.equal(new Headers(call.init.headers).get('X-HX-Request'), '1')
  assert.equal(calls.at(-1)?.init.method, 'DELETE')
  assert.deepEqual(JSON.parse(String(calls.at(-1)?.init.body)), { revision: 2 })
})
test('校验真实 unchecked 状态、候选身份字段与官方授权地址', () => {
  assert.equal(isAccount(account), true); assert.equal(isAccount({ ...account, checking: undefined }), false)
  assert.equal(isAuthorization(authorization), true); assert.equal(isAuthorization({ ...authorization, different: undefined }), false)
  assert.equal(officialAuthorizationUrl('javascript:alert(1)'), '')
  assert.equal(officialAuthorizationUrl('https://auth.openai.com.attacker.test/codex/device'), '')
  assert.equal(officialAuthorizationUrl(authorization.verificationUrl), authorization.verificationUrl)
  assert.equal(managementCapability('codex-auth'), 'settings.manage')
})
test('同邮箱不同身份也需要勾选确认，启用成功后卸载不取消', async () => {
  let activations = 0, cancellations = 0, accepted = false
  const api = fakeApi({ start: async () => ({ ...authorization, step: 'verified', candidateEmail: account.email, different: true }), activate: async (_id, acknowledged) => { activations++; accepted = acknowledged; return { ...account, status: 'ready' } }, cancel: async () => { cancellations++; return { ok: true } } })
  const view = mount(() => useAuthorization(api, 'replace', 2, events()))
  await flush(); await view.state.activate(); assert.equal(activations, 0)
  view.state.acknowledged.value = true; await view.state.activate()
  assert.equal(activations, 1); assert.equal(accepted, true)
  view.close(); await flush(); assert.equal(cancellations, 0)
})
test('卸载期间返回的新候选立即尽力取消，不再泄露状态', async () => {
  const pending = deferred<Authorization>(); const cancelled: string[] = []
  const view = mount(() => useAuthorization(fakeApi({ start: () => pending.promise, cancel: async id => { cancelled.push(id); return { ok: true } } }), 'renew', 2, events()))
  view.close(); pending.resolve(authorization); await flush()
  assert.deepEqual(cancelled, ['candidate']); assert.equal(view.state.authorization.value, undefined)
})
test('取消失败留在弹窗可重试；取消成功才关闭', async () => {
  let fail = true, closed = 0
  const view = mount(() => useAuthorization(fakeApi({ cancel: async () => { if (fail) throw new Error('连接失败'); return { ok: true } } }), 'renew', 2, { ...events(), close: () => { closed++ } }))
  await flush(); await view.state.close(); assert.equal(closed, 0); assert.match(view.state.error.value, /连接失败/); assert.equal(view.state.busy.value, false)
  fail = false; await view.state.close(); assert.equal(closed, 1); view.close()
})
test('服务重启已清理候选时404取消仍可关闭弹窗', async () => {
  let closed = 0
  const view = mount(() => useAuthorization(fakeApi({ cancel: async () => { throw new IdentityError(404, '流程已清理') } }), 'renew', 2, { ...events(), close: () => { closed++ } }))
  await flush(); await view.state.close(); assert.equal(closed, 1); assert.equal(view.state.error.value, ''); view.close()
})
test('轮询失败可恢复，重试候选检测保留服务端状态和期限', async () => {
  let fail = true
  const view = mount(() => useAuthorization(fakeApi({ poll: async () => { if (fail) throw new Error('网络异常'); return { ...authorization, step: 'failed' } } }), 'renew', 2, events()))
  await flush(); await view.state.poll(); assert.match(view.state.error.value, /网络异常/); assert.equal(view.state.step.value, 'waiting')
  fail = false; await view.state.poll(); assert.equal(view.state.step.value, 'failed')
  await view.state.retry(); assert.equal(view.state.step.value, 'checking')
  assert.ok(view.state.remaining.value > 170 && view.state.remaining.value <= 180); view.close()
})
test('请求失败与移除冲突保留原账号，读取可恢复操作', async () => {
  const view = mount(() => useAccount(fakeApi(), () => {})); await flush()
  await view.state.mutate(async () => { throw new IdentityError(409, '冲突') })
  assert.equal(view.state.account.value?.revision, 2); assert.equal(view.state.account.value?.email, account.email)
  assert.match(view.state.error.value, /重新读取/); assert.equal(view.state.busy.value, false)
  await view.state.load(); assert.equal(view.state.error.value, ''); view.close()
})
test('业务页面卸载后的迟到读取不覆盖新业务', async () => {
  const pending = deferred<Account>()
  const domestic = mount(() => useAccount(fakeApi({ get: () => pending.promise }), () => {}))
  domestic.close()
  const overseas = mount(() => useAccount(fakeApi({ get: async () => ({ ...account, email: 'overseas@example.test' }) }), () => {}))
  pending.resolve(account); await flush()
  assert.equal(domestic.state.account.value, undefined); assert.equal(overseas.state.account.value?.email, 'overseas@example.test')
  overseas.close()
})
test('重启授权先取消原候选，清理409期间自动短重试', async () => {
  let starts = 0, cancels = 0
  const view = mount(() => useAuthorization(fakeApi({ start: async () => { starts++; if (starts === 2) throw new IdentityError(409, '正在清理'); return { ...authorization, id: String(starts) } }, cancel: async () => { cancels++; return { ok: true } } }), 'renew', 2, events()))
  await flush(); await view.state.start()
  assert.equal(starts, 3); assert.equal(cancels, 1); assert.equal(view.state.authorization.value?.id, '3'); view.close()
})

for (const side of ['domestic', 'overseas'] as const) test(`${side}: 真实业务409错误体驱动清理后的自动重试`, async () => {
  let starts = 0, cancels = 0
  const api = createCodexAuthApi(side, async (_url, init) => {
    if (init?.method === 'DELETE') { cancels++; return Response.json({ ok: true }) }
    starts++
    if (starts === 2) return Response.json({ code: 'CONFLICT', message: '授权流程正在结束，请稍后重试', requestId: 'test-request' }, { status: 409 })
    return Response.json({ ...authorization, id: String(starts) })
  })
  const view = mount(() => useAuthorization(api, 'renew', 2, events()))
  await flush()
  // Real Response parsing is asynchronous; wait for initial start before the restart.
  const deadline = Date.now() + 1000
  while (view.state.busy.value && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 5))
  assert.equal(view.state.busy.value, false)
  await view.state.start()
  assert.equal(starts, 3); assert.equal(cancels, 1)
  assert.equal(view.state.authorization.value?.id, '3'); assert.equal(view.state.error.value, '')
  view.close()
})
