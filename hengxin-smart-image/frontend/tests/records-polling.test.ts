import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import * as Vue from 'vue'
import { isTaskActive } from '../src/types/api-image-edits'
type Records = ReturnType<typeof import('../src/views/hengxin/api-image-edits/use-records').useRecords>

test('真实记录逻辑隐藏停轮询，恢复等授权，终态详情低频同步，写操作立即刷新', async () => {
  const source = readFileSync(new URL('../src/views/hengxin/api-image-edits/use-records.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  let now = 1000
  let lists = 0, details = 0, verify!: () => void, nextId = 0
  let failDetail = false
  let listBarrier: Promise<void> | undefined
  const doc = Object.assign(new EventTarget(), { visibilityState: 'visible' })
  const timers = new Map<number, () => Promise<void>>()
  const bootstrap = { ready: true, locked: false }
  const apiImages = {
    list: async () => { lists++; await listBarrier; return { items: [], total: 0 } },
    task: async () => { details++; if (failDetail) throw new Error('temporary 503'); return { id: 'task', status: 'succeeded' } }
  }
  const module = { exports: {} as { useRecords: () => Records } }
  new Function('require', 'module', 'exports', 'document', 'setTimeout', 'clearTimeout', 'Date', code)(
    (name: string) => {
      if (name === 'vue') return Vue
      if (name === '@/store/modules/user') return { useUserStore: () => ({ getUserInfo: { userId: 'u' } }) }
      if (name === '@/api/api-image-edits') return { apiImages, errorText: String }
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
    assert.equal(records.selected.value, undefined); assert.match(records.detailError.value, /503/)
    failDetail = false; await poll(); await settle()
    assert(records.selected.value); assert.equal(records.detailError.value, '')
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
