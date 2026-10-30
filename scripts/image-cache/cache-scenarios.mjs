import assert from 'node:assert/strict'

export async function cacheScenarios(page, state, checks) {
  const originals = id => state.requests.filter(r => !r.small && (!id || r.id === id))
  const reset = async () => { await page.evaluate(() => window.imageTest.reset()); state.requests.length = 0 }
  const reachedServer = async id => {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (originals(id).length) return
      await new Promise(done => setTimeout(done, 10))
    }
    assert.fail(`fixture never received ${id}`)
  }
  await reset()
  state.delays.set('dedup', 120)
  const leases = await page.evaluate(async () => Promise.all(Array.from({ length: 6 }, () => window.imageTest.acquire('dedup'))))
  assert.equal(originals('dedup').filter(r => r.method === 'GET').length, 1)
  assert.equal(new Set(leases.map(l => l.url)).size, 1)
  assert(leases.every(l => l.size > 1000 && l.type === 'image/png'))
  checks.push('同URL六个并发读取共用一个GET和Blob，释放不影响其他读取者')

  await reset()
  state.delays.set('prefetch-click', 120)
  await page.evaluate(() => window.imageTest.cache.setPrefetch('same-flight', [{ url: window.imageTest.url('prefetch-click') }]))
  await page.waitForFunction(() => window.imageTest.cache.stats().active === 1)
  await page.evaluate(() => window.imageTest.acquire('prefetch-click'))
  assert.equal(originals('prefetch-click').filter(r => r.method === 'GET').length, 1)
  checks.push('预取在途时点击等待同一原图GET，无重复下载')

  for (const code of [401, 403, 404]) {
    await reset()
    await page.evaluate(() => window.imageTest.acquire('revoked'))
    state.status.set('revoked', code)
    const error = await page.evaluate(async () => {
      try { await window.imageTest.acquire('revoked'); return null } catch (e) { return e.status }
    })
    assert.equal(error, code)
    assert.equal(await page.evaluate(() => window.imageTest.cache.stats().entries), 0)
    state.status.delete('revoked')
    await page.evaluate(() => window.imageTest.acquire('revoked'))
    assert.equal(originals('revoked').at(-1).method, 'GET', 'revocation must drop page bytes before retry')
    checks.push(`${code}校验失败清空该原图；权限恢复后重新GET，HTTP缓存仍须校验`)
  }

  await reset()
  state.status.set('retry', 500)
  assert.equal(await page.evaluate(async () => {
    try { await window.imageTest.acquire('retry'); return false } catch { return true }
  }), true)
  state.status.delete('retry')
  await page.evaluate(() => window.imageTest.acquire('retry'))
  assert.equal(originals('retry').filter(r => r.method === 'GET').length, 2)
  checks.push('原图GET失败不固化错误；下一次读取成功重试')

  await reset()
  await page.evaluate(() => window.imageTest.acquire('version'))
  state.revision.set('version', 2)
  await page.evaluate(() => window.imageTest.acquire('version'))
  assert.deepEqual(originals('version').map(r => `${r.method}:${r.status}`), ['GET:200', 'HEAD:200', 'GET:200'])
  checks.push('ETag变化时HEAD发现新版本并重新获取原件')

  await reset()
  state.delays.set('stale', 300)
  await page.evaluate(() => { window.staleResult = window.imageTest.acquire('stale').then(() => 'resolved', () => 'aborted') })
  await reachedServer('stale')
  await page.evaluate(() => window.imageTest.cache.setIdentity('fixture-account-b'))
  assert.equal(await page.evaluate(() => window.staleResult), 'aborted')
  await page.waitForTimeout(350)
  assert.equal(await page.evaluate(() => window.imageTest.cache.stats().entries), 0)
  await page.evaluate(() => window.imageTest.acquire('stale'))
  await page.evaluate(() => window.imageTest.cache.setIdentity(''))
  assert.deepEqual(await page.evaluate(() => window.imageTest.cache.stats()), { entries: 0, bytes: 0, active: 0, queued: 0 })
  assert.equal(await page.evaluate(async () => {
    try { await window.imageTest.acquire('stale'); return null } catch (e) { return e.status }
  }), 401)
  checks.push('账号切换取消在途响应且不得回填；退出释放全部缓存并拒绝未登录读取')

  await reset()
  for (const id of ['queue-a', 'queue-b', 'queue-c', 'queue-d', 'new-session']) state.delays.set(id, 150)
  await page.evaluate(() => window.imageTest.cache.setPrefetch('old-session', ['queue-a','queue-b','queue-c','queue-d'].map(id => ({ url: window.imageTest.url(id) }))))
  await page.waitForFunction(() => window.imageTest.cache.stats().queued === 2)
  await page.evaluate(() => window.imageTest.cache.setPrefetch('new-session', [{ url: window.imageTest.url('new-session') }]))
  await page.waitForFunction(() => { const s = window.imageTest.cache.stats(); return s.active === 0 && s.queued === 0 && s.entries === 1 })
  assert.equal(originals('queue-c').length + originals('queue-d').length, 0)
  assert.equal(originals('new-session').filter(r => r.method === 'GET').length, 1)
  checks.push('会话切换取消旧预取队列；旧会话未开始项不发请求，新会话继续预取')

  await reset()
  for (const id of ['priority-a','priority-b','priority-c','priority-d']) state.delays.set(id, 120)
  await page.evaluate(() => {
    window.imageTest.cache.setPrefetch('priority', ['priority-a','priority-b','priority-c','priority-d'].map(id => ({ url: window.imageTest.url(id) })))
    window.clickedResult = window.imageTest.acquire('priority-d')
  })
  await page.evaluate(() => window.clickedResult)
  await page.waitForFunction(() => { const s = window.imageTest.cache.stats(); return s.active === 0 && s.queued === 0 })
  const starts = originals().filter(r => r.method === 'GET').map(r => r.id)
  assert(starts.indexOf('priority-d') < starts.indexOf('priority-c'))
  assert(state.maxActive <= 2, `max active originals ${state.maxActive}`)
  checks.push('点击将未开始项提升到后台项之前；预取最多两个原件GET并发')

  await reset()
  const bounded = await page.evaluate(async () => {
    const cache = window.imageTest.createImageCache({ maxEntries: 2, maxBytes: 2000000 })
    cache.setIdentity('bounded')
    for (const id of ['lru-a','lru-b','lru-c']) { const lease = await cache.acquire(window.imageTest.url(id)); lease.release() }
    await new Promise(done => setTimeout(done, 0))
    const after = cache.stats()
    const last = await cache.acquire(window.imageTest.url('lru-c')); last.release()
    const first = await cache.acquire(window.imageTest.url('lru-a')); first.release()
    cache.clear()
    const bytes = window.imageTest.createImageCache({ maxEntries: 40, maxBytes: 1 })
    bytes.setIdentity('bytes')
    const large = await bytes.acquire(window.imageTest.url('oversized'))
    const pinned = { size: large.blob.size, url: large.url }; large.release()
    await new Promise(done => setTimeout(done, 0))
    return { after, pinned, released: bytes.stats() }
  })
  assert.equal(bounded.after.entries, 2)
  assert.equal(originals('lru-c').at(-1).method, 'HEAD')
  assert.equal(originals('lru-a').filter(r => r.method === 'GET').length, 2)
  assert(bounded.pinned.size > 1)
  assert.equal(bounded.released.entries, 0)
  checks.push('数量LRU淘汰最旧项；超预算原图可按需查看，释放后不在内存常驻')
}
