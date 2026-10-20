import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import * as Vue from 'vue'
import { uncertainResponse } from '../src/api/api-image-edits'
import { ApiError } from '../src/api/hengxin/http'
import { isTaskActive } from '../src/types/api-image-edits'
type Records = ReturnType<typeof import('../src/views/hengxin/api-image-edits/use-records').useRecords>

test('真实记录逻辑隐藏停轮询，恢复等授权，终态详情低频同步，写操作立即刷新', async () => {
  const source = readFileSync(new URL('../src/views/hengxin/api-image-edits/use-records.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  let now = 1000
  let lists = 0, details = 0, verify!: () => void, nextId = 0
  let failDetail = false, failRetry = true
  const retryCalls: string[] = []
  let cliActivity = 'idle', deletionState = 'idle', deleteCalls = 0, failDeletionRead = false
  let listBarrier: Promise<void> | undefined
  const doc = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  const timers = new Map<number, () => Promise<void>>()
  const bootstrap = { ready: true, locked: false }
  const apiImages = {
    retry: async (_id: string, key: string) => { retryCalls.push(key); if (failRetry) throw new ApiError('UNAVAILABLE', 'secret upstream', 503) },
    list: async () => { lists++; await listBarrier; return { items: deletionState === 'deleted' ? [] : [{ id: 'task', name: '待删除任务', status: 'succeeded', cliActivity, deletionState, canDelete: deletionState !== 'deleting' }], total: deletionState === 'deleted' ? 0 : 1 } },
    task: async () => { details++; if (failDetail) throw new Error('temporary 503'); return { id: 'task', status: 'succeeded', cliActivity, deletionState } },
    remove: async () => { deleteCalls++; deletionState = 'deleting'; return { state: deletionState, message: null } },
    deletion: async () => { if (failDeletionRead) throw new Error('lost response'); return { state: deletionState, message: deletionState === 'failed' ? '删除未完成' : null } }
  }
  const module = { exports: {} as { useRecords: () => Records } }
  new Function('require', 'module', 'exports', 'document', 'setTimeout', 'clearTimeout', 'Date', code)(
    (name: string) => {
      if (name === 'vue') return Vue
      if (name === '@/store/modules/user') return { useUserStore: () => ({ getUserInfo: { userId: 'u' } }) }
      if (name === '@/api/api-image-edits') return { apiImages, errorText: String, uncertainResponse }
      if (name === '@/types/api-image-edits') return { isTaskActive }
      if (name === '@/api/hengxin/identity') return { identity: { epoch: 1, current: () => true } }
      if (name === '@/api/hengxin/bootstrap') return { bootstrap, retryBootstrap: { run: () => new Promise<void>(resolve => { verify = resolve }) } }
      throw new Error(name)
    }, module, module.exports, doc,
    (callback: () => Promise<void>) => { timers.set(++nextId, callback); return nextId },
    (id: number) => timers.delete(id), { now: () => now })
  const renderer = Vue.createRenderer<object, object>({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {},
    setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}
  })
  let records!: Records
  const app = renderer.createApp({ setup() { records = module.exports.useRecords(); return () => Vue.h('div') } })
  const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await Vue.nextTick() }
  app.mount({})
  try {
    await settle(); assert.equal(lists, 1)
    records.selectedId.value = 'task'; await settle(); assert.equal(details, 1)
    const poll = [...timers.values()][0]; timers.clear(); await poll(); await settle()
    assert.equal(lists, 2); assert.equal(details, 1)
    doc.visibilityState = 'hidden'; doc.dispatchEvent(new Event('visibilitychange'))
    assert.equal(timers.size, 0); await poll(); assert.equal(lists, 2)
    bootstrap.locked = true; doc.visibilityState = 'visible'; doc.dispatchEvent(new Event('visibilitychange'))
    await settle(); assert.equal(lists, 2)
    bootstrap.locked = false; verify(); await settle()
    assert.equal(lists, 3); assert.equal(details, 2)
    now += 30000; await poll(); assert.equal(lists, 4); assert.equal(details, 3)
    await records.action(async () => {}); assert.equal(lists, 5); assert.equal(details, 4)
    failDetail = true; records.selectedId.value = 'another'; await settle()
    assert.equal(records.selected.value, undefined); assert.match(records.detailError.value, /详情加载失败/)
    failDetail = false; await poll(); await settle()
    assert(records.selected.value); assert.equal(records.detailError.value, '')
    records.selectedId.value = 'task'; await settle()
    const lastDetail = records.selected.value
    failDetail = true; await records.loadDetail(); await settle()
    assert.equal(records.selected.value, lastDetail)
    assert.equal(records.detailError.value, '刷新失败，已保留上次进度，请重试。')
    failDetail = false; await records.loadDetail()
    cliActivity = 'queued'; await poll(); await settle()
    assert.equal(records.selected.value?.cliActivity, 'queued', '已成功API任务的CLI排队推动详情同步')
    records.selectedId.value = ''; await settle()
    cliActivity = 'running'; await poll(); await settle()
    assert.equal(records.tasks.value[0]?.cliActivity, 'running', '关闭详情后仍同步列表CLI状态')
    records.selectedId.value = 'task'; await settle()
    cliActivity = 'idle'; await poll(); await settle()
    assert.equal(records.selected.value?.cliActivity, 'idle', 'CLI结束立即移除详情提示而非等30秒')
    await records.removeTask(records.tasks.value[0]!); await settle()
    assert.equal(deleteCalls, 1); assert.equal(records.tasks.value.length, 1)
    assert.equal(records.deletedId.value, '', '删除受理不能提示成功或移除')
    failDeletionRead = true; await poll(); await settle()
    assert.equal(records.tasks.value.length, 1); assert.match(records.actionError.value, /尚未确认/)
    failDeletionRead = false; await poll(); await settle()
    assert.equal(records.actionError.value, '', '删除状态恢复后清除过期断网错误')
    deletionState = 'failed'; await poll(); await settle()
    assert.equal(records.tasks.value[0]?.deletionState, 'failed'); assert.equal(records.deletedId.value, '')
    await records.removeTask(records.tasks.value[0]!); await settle()
    assert.equal(deleteCalls, 2)
    deletionState = 'deleted'; await poll(); await settle()
    assert.equal(records.tasks.value.length, 0); assert.equal(records.deletedId.value, 'task')
    assert.equal(records.selectedId.value, '')
    await records.retry('task'); await settle()
    assert.equal(records.actionError.value, '操作未完成，请再试一次。')
    failRetry = false; await records.retry('task'); await settle()
    assert.equal(retryCalls.length, 2); assert.equal(retryCalls[0], retryCalls[1])
    assert.equal(records.actionError.value, '')
    let release!: () => void
    listBarrier = new Promise<void>(resolve => { release = resolve })
    now += 30000
    const callsBeforeHidden = details, runningPoll = poll()
    doc.visibilityState = 'hidden'; doc.dispatchEvent(new Event('visibilitychange'))
    release(); await runningPoll; await settle()
    assert.equal(details, callsBeforeHidden); assert.equal(timers.size, 0)
  } finally { app.unmount() }
  assert.equal(timers.size, 0)
})
