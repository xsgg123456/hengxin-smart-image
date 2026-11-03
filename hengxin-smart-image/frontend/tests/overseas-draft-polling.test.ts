import test from 'node:test'
import assert from 'node:assert/strict'
import { createDraftController } from '../src/views/overseas/requirement-draft-controller'
import { IdentityError } from '../src/api/identity/request'
import { flush } from './membership-test-harness'
import { fixture, fresh, deferred, clone } from './draft-polling-fixture'

test('首次读取去重；空闲及所有终态无常驻查询；写操作产生queued后恢复轮询', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture(), c = createDraftController(f.api, f.storage); t.after(() => c.dispose())
  await Promise.all([c.initialize(), c.initialize()]); assert.equal(f.data.reads, 1)
  t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 1)
  await c.mutate(async () => fresh('queued'))
  t.mock.timers.tick(1999); await flush(); assert.equal(f.data.reads, 1)
  f.data.server = fresh('running'); t.mock.timers.tick(1); await flush(); assert.equal(f.data.reads, 2)
  for (const state of ['ready', 'failed', 'cancelled'] as const) {
    await c.mutate(async () => fresh('running')); f.data.server = fresh(state)
    t.mock.timers.tick(2000); await flush(); const reads = f.data.reads
    assert.equal(c.state.server?.imports[0].state, state)
    t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, reads)
  }
})

test('慢GET不积压；完成后整整2秒才重查；排队输入优先PUT且保留本地最后输入', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  const gate = deferred<ReturnType<typeof fresh>>(), get = f.api.get
  let calls = 0
  f.api.get = async () => { calls++; return calls === 1 ? gate.promise : get() }
  t.mock.timers.tick(2000); await flush()
  const a = c.refresh(), b = c.refresh(); assert.equal(a, b)
  t.mock.timers.tick(20000); await flush(); assert.equal(calls, 1)
  c.edit({ ...c.state.fields, name: '慢查询中的输入' }); t.mock.timers.tick(500); await flush()
  assert.equal(f.data.writes, 0); assert.equal(f.storage.read()?.fields.name, '慢查询中的输入')
  gate.resolve(fresh('running')); await a; await flush()
  assert.equal(f.data.writes, 1); assert.equal(f.data.server.fields.name, '慢查询中的输入'); assert.equal(calls, 1)
  t.mock.timers.tick(1999); await flush(); assert.equal(calls, 1)
  t.mock.timers.tick(1); await flush(); assert.equal(calls, 2)
})

test('refresh遇dirty先保存；慢PUT期间读去重且后续输入再次保存完成才GET', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  const gate = deferred<void>(), save = f.api.save
  f.api.save = async (version, fields) => { await gate.promise; return save(version, fields) }
  c.edit({ ...c.state.fields, name: '第一遍' }); const pending = c.refresh(); await flush()
  assert.equal(c.state.saving, true); assert.equal(f.data.reads, 1)
  for (let n = 0; n < 5; n++) { t.mock.timers.tick(2000); await flush(); assert.equal(c.refresh(), pending) }
  c.edit({ ...c.state.fields, name: '最终字段' }); gate.resolve(); await pending; await flush()
  assert.deepEqual(f.data.events, ['GET', 'PUT', 'PUT', 'GET']); assert.equal(c.state.fields.name, '最终字段')
  assert.equal(f.storage.read()?.fields.name, '最终字段'); assert.equal(c.state.dirty, false)
})

test('保持500ms防抖；隐藏暂停GET但自动保存继续；可见仅刷新一次', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  c.setVisible(false); c.edit({ ...c.state.fields, name: '后台自动保存' })
  t.mock.timers.tick(499); await flush(); assert.equal(f.data.writes, 0)
  t.mock.timers.tick(1); await flush(); assert.equal(f.data.writes, 1)
  t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 1)
  f.data.server.imports[0].state = 'ready'; c.setVisible(true); c.setVisible(true); await flush()
  assert.equal(f.data.reads, 2); assert.equal(c.state.fields.name, '后台自动保存')
  t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 2)
})

test('连续3次查询失败暂停，隐藏恢复也不绕过；手动重试成功后恢复且保存错误不被读取清除', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('queued'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  await assert.rejects(c.mutate(async () => { throw Error('附件保存失败') })); f.data.readError = '读取断网'
  for (let n = 1; n <= 3; n++) { t.mock.timers.tick(2000); await flush(); assert.equal(c.state.queryFailures, n) }
  assert.equal(c.state.queryPaused, true); assert.match(c.state.queryError, /自动更新已暂停/); assert.equal(c.state.error, '附件保存失败')
  t.mock.timers.tick(60000); c.setVisible(false); c.setVisible(true); await flush(); assert.equal(f.data.reads, 4)
  f.data.readError = ''; await c.retryQuery(); assert.equal(f.data.reads, 5); assert.equal(c.state.queryError, ''); assert.equal(c.state.error, '附件保存失败')
  t.mock.timers.tick(2000); await flush(); assert.equal(f.data.reads, 6)
})

test('保存失败保持dirty和恢复副本，不能误记为查询失败或继续读取；手动保存后才恢复', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  f.data.saveError = '保存断网'; c.edit({ ...c.state.fields, name: '保留字段' }); t.mock.timers.tick(500); await flush()
  await c.refresh(); assert.equal(f.data.reads, 1); assert.equal(c.state.queryFailures, 0); assert.equal(c.state.queryError, '')
  assert.equal(c.state.dirty, true); assert.equal(f.storage.read()?.fields.name, '保留字段')
  t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 1)
  f.data.saveError = ''; await c.flush(); t.mock.timers.tick(2000); await flush(); assert.equal(f.data.reads, 2); assert.equal(c.state.error, '')
})

test('初始读取失败使用查询错误并可重试；成功会重置连续失败次数', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('queued'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose())
  f.data.readError = '初始断网'; await c.initialize(); assert.equal(c.state.initialized, false); assert.equal(c.state.error, ''); assert.match(c.state.queryError, /初始断网/)
  f.data.readError = ''; await c.retryQuery(); assert.equal(c.state.initialized, true)
  f.data.readError = '断网'; await c.refresh(); assert.equal(c.state.queryFailures, 1)
  f.data.readError = ''; await c.refresh(); assert.equal(c.state.queryFailures, 0)
})

test('轮询发现代次或来源变化保持恢复副本并停止；明确恢复后才继续', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  c.edit({ ...c.state.fields, name: '原字段' }); await c.flush(); const prior = clone(f.storage.read())
  f.data.server = { ...fresh('running'), id: 'new-generation' }; await c.refresh()
  assert.equal(c.state.conflict, true); assert.deepEqual(f.storage.read(), prior)
  t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 2)
  await c.resolve(false); assert.equal(c.state.server?.id, 'new-generation'); assert.equal(c.state.conflict, false)
})

test('提交期间迟到GET不合并，也不覆写提交副本；完成后不再查询或重建副本', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  const gate = deferred<ReturnType<typeof fresh>>(); f.api.get = () => gate.promise
  const pending = c.refresh(); await flush(); c.submission({ ...c.state.fields, materialIds: [] }, 'exact-key')
  gate.resolve({ ...fresh(), id: 'consumed' }); await pending
  assert.equal(c.state.server?.id, 'draft'); assert.equal(c.state.conflict, false); assert.equal(f.storage.read()?.submission?.key, 'exact-key')
  c.completed(); t.mock.timers.tick(60000); await flush(); assert.equal(f.storage.read(), undefined)
})

test('切账号卸载后迟到初始读取和状态请求无更新；取消排队读不产生未处理拒绝', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const initialized of [false, true]) {
    const f = fixture('running'), c = createDraftController(f.api, f.storage)
    if (initialized) await c.initialize()
    const gate = deferred<ReturnType<typeof fresh>>(); f.api.get = () => gate.promise
    const pending = initialized ? c.refresh() : c.initialize(); await flush(); c.dispose()
    const before = clone(c.state); gate.resolve({ ...fresh(), id: 'other-account' }); await pending
    assert.deepEqual(clone(c.state), before)
  }
  const f = fixture('running'), c = createDraftController(f.api, f.storage); await c.initialize()
  const pending = c.refresh(); c.dispose(); await pending; assert.equal(f.data.reads, 1)
})

test('读取身份失效立即暂停并上报，不伪装成保存错误', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), failures: unknown[] = [], c = createDraftController(f.api, f.storage, r => failures.push(r)); t.after(() => c.dispose()); await c.initialize()
  f.api.get = async () => { throw new IdentityError(403, '权限失效') }; await c.refresh()
  assert.equal(failures.length, 1); assert.equal(c.state.queryPaused, true); assert.equal(c.state.error, '')
})

test('暂停后用户成功发起新导入或重试附件，完整写响应重置查询暂停并继续轮询', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture('running'), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  f.data.readError = '断网'; for (let n = 0; n < 3; n++) await c.refresh()
  assert.equal(c.state.queryPaused, true); f.data.readError = ''
  await c.mutate(async () => fresh('queued')); assert.equal(c.state.queryPaused, false); assert.equal(c.state.queryError, '')
  t.mock.timers.tick(2000); await flush(); assert.equal(f.data.reads, 5)
})

test('确认框期间恢复可见，将唯一刷新延后到解锁；空闲草稿也读取一次', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture(), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  c.setPaused(true); c.setVisible(false); c.setVisible(true); await flush(); assert.equal(f.data.reads, 1)
  c.setPaused(false); await flush(); assert.equal(f.data.reads, 2)
  c.setPaused(false); t.mock.timers.tick(60000); await flush(); assert.equal(f.data.reads, 2)
})

test('上传在GET旧快照之后完成，上传事件等待当前读取后合并一次新查询', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture(), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  const gate = deferred<ReturnType<typeof fresh>>(), get = f.api.get
  f.api.get = () => gate.promise; const oldRead = c.refresh(); await flush()
  f.data.server.materials.push({ id: 'new-upload', kind: 'requirement', name: 'file.pptx', sizeBytes: 30, contentType: 'application/octet-stream', status: 'ready', taskId: null, createdAt: '' })
  const uploads = [c.refreshAfterUpload(), c.refreshAfterUpload()]; f.api.get = get; gate.resolve(fresh())
  await oldRead; await Promise.all(uploads); assert.equal(f.data.reads, 2); assert.equal(c.state.server?.materials[0].id, 'new-upload')
})

test('隐藏或卸载阻止上传补读，恢复可见重新读取；提交错误恢复可显式查询', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  for (const disposed of [false, true]) {
    const f = fixture(), c = createDraftController(f.api, f.storage); await c.initialize()
    const gate = deferred<ReturnType<typeof fresh>>(), get = f.api.get
    f.api.get = () => gate.promise; const pending = c.refresh(); await flush()
    const upload = c.refreshAfterUpload(); if (disposed) c.dispose(); else c.setVisible(false)
    f.api.get = get; gate.resolve(fresh()); await pending; await upload; assert.equal(f.data.reads, 1)
    if (!disposed) { c.setVisible(true); await flush(); assert.equal(f.data.reads, 2); c.dispose() }
  }
  const f = fixture(), c = createDraftController(f.api, f.storage); t.after(() => c.dispose()); await c.initialize()
  c.setPaused(true); c.submission({ ...c.state.fields, materialIds: [] }, 'key'); c.clearSubmission()
  await c.refresh(); assert.equal(f.data.reads, 2, '提交catch期间UI仍busy，明确刷新仍应执行')
})
