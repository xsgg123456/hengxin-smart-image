import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createImageCache } from '../src/api/overseas/image-cache'
import { PREFETCH_IMAGE_BYTES } from '../src/api/overseas/image-cache-http'

const tick = async () => { for (let i = 0; i < 30; i++) await Promise.resolve() }
const content = (text = 'original-bytes', etag = '"v1"') => new Response(text, { headers: { ETag: etag, 'Content-Type': 'image/png', 'Content-Length': String(text.length) } })
function cache(fetcher: typeof fetch, limits = {}) {
  const revoked: string[] = []; let sequence = 0
  const instance = createImageCache({ fetcher, createUrl: () => `blob:${++sequence}`, revokeUrl: url => revoked.push(url), ...limits })
  instance.setIdentity('account-a')
  return { instance, revoked }
}

test('预取和点击共享在途原图，复开仅HEAD校验ETag，原字节与私有缓存请求保持', async () => {
  const calls: { url: string; options?: RequestInit }[] = []; let finish!: (value: Response) => void
  const { instance, revoked } = cache(async (url, options) => {
    calls.push({ url: String(url), options })
    return options?.method === 'HEAD' ? content() : new Promise(resolve => { finish = resolve })
  })
  instance.setPrefetch('session', [{ url: '/original' }]); await tick()
  const first = instance.acquire('/original'), second = instance.acquire('/original'); await tick()
  finish(content()); const [a, b] = await Promise.all([first, second])
  assert.equal(await a.blob.text(), 'original-bytes'); assert.equal(a.url, b.url)
  a.release(); assert.equal(revoked.length, 0); b.release(); assert.equal(revoked.length, 1)
  const reopened = await instance.acquire('/original'); reopened.release()
  assert.deepEqual(calls.map(c => c.options?.method), ['HEAD', 'GET', 'HEAD'])
  assert.equal(new Headers(calls[2].options?.headers).get('If-None-Match'), '"v1"')
  assert.ok(calls.every(c => c.options?.credentials === 'include' && c.options.cache === 'no-cache'))
  instance.clear()
})

test('点击晋升队列，最多两个任务；切会话取消无用队列且迟到预取不能回填', async () => {
  const calls: string[] = [], finishes = new Map<string, (value: Response) => void>()
  const { instance } = cache(async (url, options) => {
    calls.push(`${options?.method}:${url}`)
    if (options?.method === 'HEAD') return content()
    return new Promise(resolve => finishes.set(String(url), resolve))
  })
  instance.setPrefetch('old', ['a', 'b', 'c', 'd'].map(url => ({ url }))); await tick()
  assert.equal(instance.stats().active, 2)
  const clicked = instance.acquire('d'); await tick(); finishes.get('a')!(content()); await tick()
  assert.ok(calls.includes('GET:d')); assert.ok(!calls.includes('GET:c'))
  instance.setPrefetch('new', []); finishes.get('b')!(content()); finishes.get('d')!(content())
  const lease = await clicked; lease.release(); await tick()
  assert.ok(!calls.includes('GET:c')); assert.equal(instance.stats().entries, 2)
  instance.clear()
})

test('账号切换取消旧读取并清空Blob和URL，忽略不遵守Abort的迟到响应', async () => {
  let resolve!: (value: Response) => void
  const { instance, revoked } = cache(async url => String(url) === 'cached' ? content() : new Promise(done => { resolve = done }))
  const cached = await instance.acquire('cached')
  const late = instance.acquire('late'); const rejected = assert.rejects(late, { name: 'AbortError' }); await tick()
  instance.setIdentity('account-b'); assert.deepEqual(revoked, [cached.url]); resolve(content()); await rejected; await tick()
  assert.equal(instance.stats().entries, 0); cached.release(); assert.equal(revoked.length, 1)
  instance.setIdentity(''); await assert.rejects(instance.acquire('cached'), { status: 401 })
})

test('容量按字节及数量淘汰，当前图保持；释放巨大原图后回到预算', async () => {
  const { instance, revoked } = cache(async url => content(String(url)), { maxBytes: 8, maxEntries: 2 })
  const current = await instance.acquire('aaaa')
  const b = await instance.acquire('bbbb'); b.release(); await tick()
  const c = await instance.acquire('cccc'); c.release(); await tick()
  assert.equal(instance.stats().bytes, 8); assert.equal(instance.stats().entries, 2)
  assert.ok(!revoked.includes(current.url)); current.release()
  const huge = await instance.acquire('0123456789012345'); await tick()
  assert.equal(instance.stats().entries, 1); assert.equal(instance.stats().bytes, 16)
  huge.release(); assert.equal(instance.stats().bytes, 0)
})

test('版本改变重取原件，401/403/404清除旧缓存，错误后可重试', async () => {
  let etag = '"v1"', status = 200, gets = 0
  const { instance } = cache(async (_url, options) => {
    if (status !== 200) return new Response(null, { status })
    if (options?.method === 'GET') gets++
    return content(etag, etag)
  })
  let lease = await instance.acquire('a'); lease.release(); etag = '"v2"'
  lease = await instance.acquire('a'); assert.equal(await lease.blob.text(), etag); lease.release(); assert.equal(gets, 2)
  for (const code of [401, 403, 404]) {
    status = code; await assert.rejects(instance.acquire('a'), { status: code }); assert.equal(instance.stats().entries, 0)
    status = 200; lease = await instance.acquire('a'); lease.release()
  }
  instance.clear()
})

test('304校验复用且不传输原件；无ETag不能盲用缓存', async () => {
  let gets = 0
  const { instance } = cache(async (_url, options) => options?.method === 'HEAD' ? new Response(null, { status: 304 }) : (gets++, content()))
  let lease = await instance.acquire('a'); lease.release(); lease = await instance.acquire('a'); lease.release(); assert.equal(gets, 1); instance.clear()
  const noTag = cache(async () => { gets++; return new Response('bytes') }).instance
  lease = await noTag.acquire('a'); lease.release(); lease = await noTag.acquire('a'); lease.release(); assert.equal(gets, 4); noTag.clear()
})

test('已知大图跳过预取，HEAD大图不GET，缺长度流读取超限也不保留', async () => {
  const calls: string[] = []
  const { instance } = cache(async (url, options) => {
    calls.push(`${options?.method}:${url}`)
    if (String(url) === 'head-big') return new Response(null, { headers: { 'Content-Length': String(PREFETCH_IMAGE_BYTES + 1) } })
    if (options?.method === 'HEAD') return new Response(null)
    return new Response(new Uint8Array(PREFETCH_IMAGE_BYTES + 1))
  })
  instance.setPrefetch('s', [{ url: 'known-big', size: PREFETCH_IMAGE_BYTES + 1 }, { url: 'head-big' }, { url: 'stream-big' }]); await tick()
  assert.ok(!calls.some(call => call.includes('known-big'))); assert.ok(!calls.includes('GET:head-big'))
  assert.equal(instance.stats().entries, 0); instance.clear()
})

test('单个消费者取消不影响共享读取，全部取消不留后台请求', async () => {
  let finish!: (value: Response) => void
  const { instance } = cache(async () => new Promise(resolve => { finish = resolve }))
  const controller = new AbortController(), a = instance.acquire('a', { signal: controller.signal }), b = instance.acquire('a')
  const rejected = assert.rejects(a, { name: 'AbortError' }); await tick(); controller.abort(); await rejected
  finish(content()); const lease = await b; lease.release(); instance.clear()
  const only = new AbortController(), cancelled = instance.acquire('b', { signal: only.signal }); const result = assert.rejects(cancelled, { name: 'AbortError' })
  await tick(); only.abort(); await result; finish(content()); await tick(); assert.equal(instance.stats().entries, 0)
})

test('缓存校验在途期间不被其他完成请求淘汰，回填计数与原图租约保持一致', async () => {
  let finish!: (value: Response) => void
  const { instance } = cache(async (url, options) => String(url) === 'a' && options?.method === 'HEAD'
    ? new Promise(resolve => { finish = resolve }) : content('1234'), { maxBytes: 4, maxEntries: 1 })
  const old = await instance.acquire('a'); old.release(); await tick()
  const checking = instance.acquire('a'); await tick()
  const newer = await instance.acquire('b'); newer.release(); await tick()
  finish(content('1234')); const protectedLease = await checking; await tick()
  assert.equal(instance.stats().bytes, 4); assert.equal(instance.stats().entries, 1)
  assert.equal(await protectedLease.blob.text(), '1234'); protectedLease.release(); instance.clear()
})


test('独立预取owner共享两并发和在途，归档筛选/关闭不取消工作台或另一个查看器', async () => {
  const calls: string[] = [], signals = new Map<string, AbortSignal>(), finishes = new Map<string, (value: Response) => void>()
  const { instance } = cache(async (url, options) => {
    calls.push(`${options?.method}:${url}`); signals.set(String(url), options!.signal!)
    if (options?.method === 'HEAD') return content()
    return new Promise(resolve => finishes.set(String(url), resolve))
  })
  const detail = instance.createPrefetch(), viewer = instance.createPrefetch()
  instance.setPrefetch('studio', [{ url: 'studio' }])
  detail.update('archive', [{ url: 'a' }, { url: 'b' }]); await tick()
  viewer.update('archive', [{ url: 'a' }]); detail.dispose(); await tick()
  assert.equal(signals.get('studio')!.aborted, false); assert.equal(signals.get('a')!.aborted, false)
  assert.equal(instance.stats().active, 2); assert.ok(!calls.includes('GET:b'))
  viewer.dispose(); assert.equal(signals.get('a')!.aborted, true); assert.equal(signals.get('studio')!.aborted, false)
  finishes.get('studio')!(content()); finishes.get('a')!(content()); await tick()
  assert.equal(instance.stats().entries, 1); instance.clear()
})

test('预取晋升后切图取消消费者仍保留套图需要的请求，离开最后owner才取消', async () => {
  let finish!: (response: Response) => void, signal!: AbortSignal
  const { instance } = cache(async (_url, options) => {
    signal = options!.signal!; return options?.method === 'HEAD' ? content() : new Promise(resolve => { finish = resolve })
  })
  const owner = instance.createPrefetch(); owner.update('archive', [{ url: 'a' }]); await tick()
  const controller = new AbortController(), clicked = instance.acquire('a', { signal: controller.signal })
  const rejected = assert.rejects(clicked, { name: 'AbortError' }); controller.abort(); await rejected
  assert.equal(signal.aborted, false)
  owner.dispose(); assert.equal(signal.aborted, true); finish(content()); await tick()
  assert.equal(instance.stats().entries, 0)
})

test('按归档前缀失效清理整套缓存和在途，不影响同名图或其他业务', async () => {
  const { instance, revoked } = cache(async () => content())
  const a = await instance.acquire('/archives/a/pictures/x'), b = await instance.acquire('/archives/ab/pictures/x')
  instance.invalidatePrefix('/archives/a/pictures/')
  assert.deepEqual(revoked, [a.url]); assert.equal(instance.stats().entries, 1)
  a.release(); b.release(); instance.clear()
})


test('归档后台预取撤权即清理整套缓存，工作台缓存保持', async () => {
  const { instance } = cache(async url => String(url).endsWith('/denied') ? new Response(null, { status:403 }) : content())
  const a = await instance.acquire('/archives/a/cached'); a.release()
  const studio = await instance.acquire('/studio/image'); studio.release(); await tick()
  const errors: unknown[] = []
  const owner = instance.createPrefetch(reason => { errors.push(reason); instance.invalidatePrefix('/archives/a/') })
  owner.update('archive', [{ url:'/archives/a/denied' }, { url:'/archives/a/later' }]); await tick()
  assert.equal(errors.length,1); assert.equal(instance.stats().entries,1)
  owner.dispose(); instance.clear()
})
