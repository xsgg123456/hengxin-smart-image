import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, nextTick } from 'vue'
import { useRetention } from '../src/views/hengxin/admin/use-retention'
import { identity } from '../src/api/hengxin/identity'
import { ApiError } from '../src/api/hengxin/http'
import type { RetentionApi, RetentionRecords, RetentionRow, RetentionSummary } from '../src/types/retention'
import { mount, flush } from './membership-test-harness'
import { summary, row, records } from './retention-fixtures'
const deferred = <T>() => { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((yes,no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function setup(overrides: Partial<RetentionApi> = {}) {
  let state!: ReturnType<typeof useRetention>
  const api = { summary: async () => summary(), records: async () => records(), detail: async () => row(), ...overrides }
  const view = mount(defineComponent({ setup() { state = useRetention(api); return () => h('span') } }))
  return { state, view }
}
test('真实查询状态处理筛选并发、分页复位与日期，不允许迟到响应覆盖', async () => {
  const requests: { query: Record<string, unknown>; task: ReturnType<typeof deferred<RetentionRecords>> }[] = []
  const { state, view } = setup({ records: query => { const task = deferred<RetentionRecords>(); requests.push({ query: { ...query }, task }); return task.promise } })
  try {
    state.query.page = 3; await nextTick()
    state.query.keyword = '最新'; state.dates.value = ['2026-10-20', '2026-10-21']; await nextTick()
    assert.equal(state.query.page, 1)
    assert.equal(requests.at(-1)!.query.dateTo, '2026-10-21')
    requests.at(-1)!.task.resolve({ ...records(), items: [{ ...row(), taskName: '最新' }] }); await flush()
    requests[0].task.resolve(records()); await flush(); assert.equal(state.records.value?.items[0].taskName, '最新')
    state.query.tab = 'pending'; await nextTick(); assert.equal(state.query.keyword, ''); assert.equal(state.query.dateFrom, undefined); assert.equal(state.records.value, undefined)
  } finally { view.close() }
})
test('刷新失败显式过期，403清旧快照；详情按detailTab读取并阻止关闭后迟到', async () => {
  let failed = false; let forbidden = false
  const detail = deferred<RetentionRow>(); const seen: string[] = []
  const { state, view } = setup({ summary: async () => { if (failed) throw new Error('网络失败'); return summary() }, records: async () => { if (forbidden) throw new ApiError('FORBIDDEN','无权限',403); if (failed) throw new Error('网络失败'); return records() }, detail: (id, tab) => { seen.push(id, tab); return detail.promise } })
  try {
    await flush(); failed = true; await state.refresh()
    assert.ok(state.summary.value); assert.ok(state.records.value); assert.equal(state.summaryError.value, '网络失败'); assert.equal(state.recordsError.value, '网络失败')
    forbidden = true; await state.refresh(); assert.equal(state.records.value, undefined)
    state.query.tab = 'pending'; const pending = state.openDetail(row()); assert.deepEqual(seen, ['receipt-1', 'history'])
    state.closeDetail(); detail.resolve(row()); await pending; assert.equal(state.selected.value, undefined); assert.equal(state.detailOpen.value, false)
  } finally { view.close() }
})
test('首次失败保持未知，身份改变清除所有快照/抽屉并拒绝旧请求', async () => {
  const pending = deferred<RetentionSummary>()
  const { state, view } = setup({ summary: () => pending.promise })
  try {
    await flush(); await state.openDetail(row()); assert.ok(state.selected.value)
    identity.advance('changed'); assert.equal(state.records.value, undefined); assert.equal(state.selected.value, undefined); assert.equal(state.detailOpen.value, false)
    pending.resolve(summary()); await flush(); assert.equal(state.summary.value, undefined); assert.match(state.summaryError.value, /身份已变化/)
  } finally { view.close() }
  const failed = setup({ summary: async () => { throw new Error('无法连接') }, records: async () => { throw new Error('无法连接') } })
  try { await flush(); assert.equal(failed.state.summary.value, undefined); assert.equal(failed.state.records.value, undefined); assert.equal(failed.state.summaryError.value, '无法连接') } finally { failed.view.close() }
})
test('15秒轮询、开关、隐藏页暂停、卸载与身份改变停止计时', async t => {
  t.mock.timers.enable({ apis: ['setInterval'] })
  const old = Object.getOwnPropertyDescriptor(globalThis, 'document'); const doc = { hidden: false }
  Object.defineProperty(globalThis, 'document', { value: doc, configurable: true })
  let reads = 0
  const { state, view } = setup({ summary: async () => { reads++; return summary() } })
  try {
    await flush(); assert.equal(reads, 1)
    t.mock.timers.tick(15000); await flush(); assert.equal(reads, 2)
    doc.hidden = true; t.mock.timers.tick(30000); await flush(); assert.equal(reads, 2)
    doc.hidden = false; state.auto.value = false; t.mock.timers.tick(15000); await flush(); assert.equal(reads, 2)
    state.auto.value = true; t.mock.timers.tick(15000); await flush(); assert.equal(reads, 3)
    identity.advance('changed'); t.mock.timers.tick(30000); await flush(); assert.equal(reads, 3)
    view.close(); t.mock.timers.tick(15000); await flush(); assert.equal(reads, 3)
    const next = setup({ summary: async () => { reads++; return summary() } })
    await flush(); assert.equal(reads, 4); next.view.close()
    t.mock.timers.tick(30000); await flush(); assert.equal(reads, 4, '未切身份直接卸载同样停止轮询')
  } finally { view.close(); if (old) Object.defineProperty(globalThis, 'document', old); else Reflect.deleteProperty(globalThis, 'document'); t.mock.timers.reset() }
})
