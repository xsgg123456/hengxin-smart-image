import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createIdentity, identity, StaleIdentityError } from '../src/api/hengxin/identity'
import { createRequest, ApiError } from '../src/api/hengxin/http'
import { createBootstrapRunner } from '../src/api/hengxin/bootstrap-runner'
import { installIdentityLifecycle } from '../src/api/hengxin/identity-lifecycle'
import { readIdentityBlob } from '../src/api/hengxin/identity-download'
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
const valid = (value: unknown): value is object => !!value && typeof value === 'object'
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { resolve, promise } }

test('旧读取成功、401及响应体晚到均不能影响新身份，GET被取消', async () => {
  for (const status of [200, 401]) {
    const result = deferred<Response>(); let signal: AbortSignal | null | undefined
    const request = createRequest('/api', async (_url, init) => { signal = init?.signal; return result.promise })
    const pending = request('/tasks', valid)
    identity.advance('changed'); const epoch = identity.epoch
    assert.equal(signal?.aborted, true)
    result.resolve(json({}, status))
    await assert.rejects(pending, StaleIdentityError)
    assert.equal(identity.epoch, epoch)
  }
  const body = deferred<unknown>()
  const response = json({}); response.json = () => body.promise
  const pending = createRequest('/api', async () => response)('/tasks', valid)
  await new Promise(resolve => setImmediate(resolve))
  identity.advance('changed'); body.resolve({ private: 'A' })
  await assert.rejects(pending, StaleIdentityError)
})

test('普通403仅核验身份，禁用403统一失效；不猜测普通图片错误', async () => {
  let probes = 0
  identity.configureProbe(async () => { probes++ })
  const epoch = identity.epoch
  await assert.rejects(createRequest('/api', async () => json({}, 403))('/admin', valid), ApiError)
  assert.equal(identity.epoch, epoch); assert.equal(probes, 1)
  identity.configureProbe(async () => { throw new ApiError('DISABLED', '禁用', 403) })
  await identity.verify(epoch)
  assert.equal(identity.epoch, epoch + 1)
  const current = identity.epoch
  identity.configureProbe(async () => { throw new Error('offline') })
  await identity.verify(current)
  assert.equal(identity.epoch, current)
})

test('普通403核验期间换号及旧响应体解析失败均返回代次失效', async () => {
  for (const binary of [false, true]) {
    const probe = deferred<unknown>()
    identity.configureProbe(() => probe.promise)
    const fetcher = async () => json({}, 403)
    const pending = binary ? readIdentityBlob('/image', {}, fetcher) : createRequest('/api', fetcher)('/admin', valid)
    await new Promise(resolve => setImmediate(resolve))
    identity.advance('changed'); const epoch = identity.epoch
    probe.resolve({})
    await assert.rejects(pending, StaleIdentityError)
    assert.equal(identity.epoch, epoch)
  }
  const body = deferred<unknown>()
  const response = json({}); response.json = async () => { await body.promise; throw new Error('invalid JSON') }
  const pending = createRequest('/api', async () => response)('/tasks', valid)
  await new Promise(resolve => setImmediate(resolve))
  identity.advance('changed'); body.resolve({})
  await assert.rejects(pending, StaleIdentityError)
})

test('44张图片并发失败仅一轮核验，限频、旧代次及晚到核验隔离', async () => {
  const session = createIdentity(), done = deferred<unknown>(); let probes = 0
  session.configureProbe(() => { probes++; return done.promise })
  const pending = Array.from({ length: 44 }, () => session.verify(0, true))
  await Promise.resolve(); assert.equal(probes, 1)
  done.resolve({}); await Promise.all(pending)
  await session.verify(0, true); assert.equal(probes, 1)
  session.advance('changed'); await session.verify(0, true); assert.equal(probes, 1)
  const old = session.epoch, failure = deferred<unknown>()
  session.configureProbe(async () => { await failure.promise; throw new ApiError('DISABLED', '', 403) })
  const stale = session.verify(old); session.advance('changed'); failure.resolve({}); await stale
  assert.equal(session.epoch, old + 1)
})

test('收费写请求不被取消，旧响应按不确定结果拒收', async () => {
  const result = deferred<Response>(); let signal: AbortSignal | null | undefined
  const pending = createRequest('/api', async (_url, init) => { signal = init?.signal; return result.promise })('/tasks', valid, 'POST', {}, 10000, { 'Idempotency-Key': 'same-key' })
  identity.advance('changed'); assert.equal(signal?.aborted, false)
  result.resolve(json({ taskId: 'accepted' })); await assert.rejects(pending, error => error instanceof StaleIdentityError && error.status === 0)
})

test('启动去重且旧A finally不解锁B，新身份无需等待旧读取', async () => {
  const a = deferred<string>(), b = deferred<string>(); let calls = 0, loading = false; const accepted: string[] = []
  const run = createBootstrapRunner({ load: () => (++calls === 1 ? a.promise : b.promise), start: () => { loading = true }, accept: value => { accepted.push(value) }, fail: () => {}, finish: () => { loading = false } })
  const old = run(); assert.equal(run(), old); await Promise.resolve()
  identity.advance('changed'); const next = run(); await Promise.resolve()
  a.resolve('A'); await old; assert.equal(loading, true); assert.deepEqual(accepted, [])
  b.resolve('B'); await next; assert.deepEqual(accepted, ['B']); assert.equal(loading, false)
})

test('隐藏和bfcache恢复先锁DOM再重验，跨标签失效不广播回环', async () => {
  const win = new EventTarget(), doc = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  const events: string[] = []
  const dispose = installIdentityLifecycle({ window: win as Window, document: doc as unknown as Document, lock: () => { events.push('lock') }, resume: async () => { events.push('verify') } })
  doc.visibilityState = 'hidden'; doc.dispatchEvent(new Event('visibilitychange'))
  doc.visibilityState = 'visible'; doc.dispatchEvent(new Event('visibilitychange'))
  assert.deepEqual(events, ['lock', 'lock', 'verify'])
  events.length = 0
  win.dispatchEvent(Object.assign(new Event('pageshow'), { persisted: true }))
  assert.deepEqual(events, ['lock', 'lock', 'verify'])
  const epoch = identity.epoch
  win.dispatchEvent(Object.assign(new Event('storage'), { key: 'hengxin:logout', newValue: 'notice' }))
  assert.equal(identity.epoch, epoch + 1)
  dispose()
})
