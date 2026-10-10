import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import * as Vue from 'vue'
import { isTaskActive } from '../src/types/api-image-edits'

type Records = ReturnType<typeof import('../src/views/hengxin/api-image-edits/use-records').useRecords>
type Query = { page: number; pageSize: number; search: string; status: string }
type Result = { items: { id: string }[]; total: number }
test('记录分页真实传参、切换回首页保留筛选、删除纠页、拒绝过期响应且失败可重试', async () => {
  const source = readFileSync(new URL('../src/views/hengxin/api-image-edits/use-records.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const queries: Query[] = [], pending: { query: Query; resolve: (value: Result) => void; reject: (error: Error) => void }[] = []
  const timers = new Map<number, () => void>(); let nextId = 0
  const apiImages = { list: (query: Query) => { queries.push({ ...query }); return new Promise<Result>((resolve, reject) => pending.push({ query, resolve, reject })) } }
  const module = { exports: {} as { useRecords: () => Records } }
  new Function('require', 'module', 'exports', 'document', 'setTimeout', 'clearTimeout', code)(
    (name: string) => {
      if (name === 'vue') return Vue
      if (name === '@/store/modules/user') return { useUserStore: () => ({ getUserInfo: { userId: 'u' } }) }
      if (name === '@/api/api-image-edits') return { apiImages, errorText: String }
      if (name === '@/types/api-image-edits') return { isTaskActive }
      if (name === '@/api/hengxin/identity') return { identity: { epoch: 1, current: () => true } }
      if (name === '@/api/hengxin/bootstrap') return { bootstrap: { ready: false, locked: false } }
      throw new Error(name)
    }, module, module.exports, Object.assign(new EventTarget(), { visibilityState: 'visible' }),
    (fn: () => void) => { timers.set(++nextId, fn); return nextId }, (id: number) => timers.delete(id))
  const renderer = Vue.createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {} })
  let records!: Records
  const app = renderer.createApp({ setup() { records = module.exports.useRecords(); return () => Vue.h('div') } })
  const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
  const answer = async (total = 101, id = 'latest') => { pending.shift()!.resolve({ items: [{ id }], total }); await flush() }
  app.mount({})
  try {
    assert.deepEqual(queries[0], { page: 1, pageSize: 20, search: '', status: '' }); await answer()
    records.filter.value = 'succeeded'; await flush(); await answer()
    records.search.value = '产品'; await flush(); for (const fn of timers.values()) fn(); timers.clear(); await flush(); await answer()
    for (const size of [50, 100, 20]) {
      records.page.value = 2; await flush(); await answer()
      const count = queries.length
      records.pageSize.value = size; await flush()
      assert.equal(queries.length, count + 1)
      assert.deepEqual(queries.at(-1), { page: 1, pageSize: size, search: '产品', status: 'succeeded' }); await answer()
    }
    records.pageSize.value = 50; await flush(); await answer()
    records.page.value = 3; await flush()
    pending.shift()!.resolve({ items: [], total: 99 }); await flush()
    assert.equal(queries.at(-1)!.page, 2); assert.equal(queries.at(-1)!.pageSize, 50); await answer(99)
    const slow = records.load(); await flush(); const old = pending.shift()!
    records.pageSize.value = 100; await flush(); await answer(99, 'new')
    old.resolve({ items: [{ id: 'stale' }], total: 200 }); await slow; await flush()
    assert.equal(records.tasks.value[0]!.id, 'new'); assert.equal(records.total.value, 99)
    const failed = records.load(); pending.shift()!.reject(new Error('offline')); await failed
    assert.match(records.error.value, /offline/)
    const retry = records.load(); await answer(99, 'recovered'); await retry; assert.equal(records.error.value, '')
    const staleSearch = records.load(); const prior = pending.shift()!
    records.search.value = '新的搜索'; await flush(); prior.resolve({ items: [{ id: 'stale-search' }], total: 1 }); await staleSearch
    assert.equal(records.tasks.value[0]!.id, 'recovered')
    records.pageSize.value = 20; await flush(); assert.equal(timers.size, 0)
    assert.equal(queries.at(-1)!.search, '新的搜索'); await answer()
  } finally { app.unmount() }
  assert.equal(timers.size, 0)
})
