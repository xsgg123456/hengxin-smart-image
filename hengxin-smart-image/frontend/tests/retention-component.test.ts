import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent, h, inject, provide, reactive, nextTick } from 'vue'
import { compile, mount, find, all, text, simple, update, flush, click } from './membership-test-harness'
import { useRetention } from '../src/views/hengxin/admin/use-retention'
import * as presenter from '../src/views/hengxin/admin/retention-presenter'
import type { RetentionApi, RetentionQuery, RetentionRow } from '../src/types/retention'
import { summary, row, records } from './retention-fixtures'
const element = Object.fromEntries(['ElAlert','ElButton','ElCard','ElDatePicker','ElDescriptions','ElDescriptionsItem','ElEmpty','ElInput','ElOption','ElPagination','ElSelect','ElSkeleton','ElSwitch','ElTabs','ElTabPane','ElTag'].map(name => [name, simple(name)]))
element.ElDrawer = defineComponent({ props: ['modelValue'], setup: (p, { slots }) => () => p.modelValue ? h('ElDrawer', slots.default?.()) : null })
element.ElTable = defineComponent({ props: ['data'], setup(p, { slots }) { provide('rows', () => p.data); return () => h('ElTable', slots.default?.()) } })
element.ElTableColumn = defineComponent({ setup(_p, { slots }) { const rows = inject<() => RetentionRow[]>('rows')!; return () => h('ElTableColumn', rows().flatMap(row => slots.default?.({ row }) || [])) } })
const deps = { 'element-plus': element, './retention-presenter': presenter }
const detail = compile('views/hengxin/admin/RetentionDetail.vue', deps)
const service = compile('views/hengxin/admin/RetentionService.vue', deps)
const policy = compile('views/hengxin/admin/RetentionPolicy.vue', deps)
function page(api: RetentionApi) {
  return compile('views/hengxin/admin/retention.vue', { ...deps,
    '@/api/retention': { retentionApi: api }, './use-retention': { useRetention },
    './RetentionDetail.vue': { default: detail }, './RetentionService.vue': { default: service }, './RetentionPolicy.vue': { default: policy }
  })
}
function windowStub() {
  const old = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { innerWidth: 1280, addEventListener() {}, removeEventListener() {} } })
  return () => { if (old) Object.defineProperty(globalThis, 'window', old); else Reflect.deleteProperty(globalThis, 'window') }
}
test('正式组件展示真实服务/四卡，筛选、日期、分页、详情、规则均接API', async () => {
  const restore = windowStub(); const queries: RetentionQuery[] = []; const details: string[] = []
  const view = mount(page({ summary: async () => summary(), records: async query => { queries.push(query); return { ...records(), total: 45, page: query.page, pageSize: query.pageSize } }, detail: async (id, tab) => { details.push(id, tab); return row() } }))
  try {
    await flush()
    assert.match(text(view.root), /服务在线/); assert.match(text(view.root), /今日缓存清理成功/); assert.match(text(view.root), /今日历史清理成功/)
    assert.match(text(view.root), /删除任务仍保留摘要/); assert.match(text(view.root), /2026-10-21 14:00:20/)
    update(find(view.root, 'ElInput', '搜索任务'), '任务名'); update(find(view.root, 'ElSelect', '清理类型'), 'history')
    update(find(view.root, 'ElSelect', '处理结果'), 'retry'); update(find(view.root, 'ElDatePicker', '处理日期范围'), ['2026-10-20','2026-10-21'])
    await flush(); assert.equal(queries.at(-1)?.keyword, '任务名'); assert.equal(queries.at(-1)?.kind, 'history'); assert.equal(queries.at(-1)?.dateTo, '2026-10-21')
    ;(find(view.root, 'ElPagination').props['onUpdate:currentPage'] as (v: number) => void)(2)
    await flush(); assert.equal(queries.at(-1)?.page, 2)
    click(view.root, '详情'); await flush(); assert.deepEqual(details, ['receipt-1', 'history']); assert.match(text(find(view.root,'ElDrawer')), /任务已删除，清理摘要保留/)
    click(view.root, '查看保留规则'); await flush(); assert.match(text(view.root), /3600 秒/); assert.match(text(view.root), /25 个会话及 25 个对象回执/)
    update(find(view.root, 'ElTabs'), 'pending'); await flush(); assert.equal(queries.at(-1)?.tab, 'pending'); assert.equal(queries.at(-1)?.keyword, '')
    assert.ok(find(view.root,'ElDatePicker','到期日期范围'))
    assert.equal(all(view.root).some(n => n.tag === 'ElSelect' && n.props['aria-label'] === '预览场景'), false)
  } finally { view.close(); restore() }
})
test('正式页面首次加载/错误/空态完整；刷新失败保留已过期快照', async () => {
  const restore = windowStub(); let fail = false
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const view = mount(page({ summary: async () => { await gate; if (fail) throw new Error('测试断网'); return summary() }, records: async () => { await gate; if (fail) throw new Error('列表断网'); return { ...records(), items: [], total: 0 } }, detail: async () => row() }))
  try {
    await nextTick(); assert.ok(find(view.root,'ElSkeleton')); release(); await flush(); assert.equal(find(view.root,'ElTable').props['empty-text'],'暂无符合条件的记录')
    fail = true; click(view.root,'刷新状态'); await flush()
    assert.match(text(view.root),/快照已过期/)
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && String(n.props.title).includes('测试断网')))
    assert.match(text(view.root),/快照过期 · 当前状态未知/)
    assert.equal(all(view.root).find(n => n.tag === 'ElTag' && text(n).includes('快照过期'))?.props.type, 'warning')
  } finally { view.close() }
  const unknown = mount(page({ summary: async () => { throw new Error('不可用') }, records: async () => { throw new Error('不可用') }, detail: async () => row() }))
  try { await flush(); assert.match(text(unknown.root), /状态未知/); assert.match(text(unknown.root), /记录数量未知/); assert.equal(find(unknown.root,'ElTable').props['empty-text'],'读取失败，请刷新重试') } finally { unknown.close(); restore() }
})
test('详情组件加载和失败不泄漏旧记录，未知服务不宣称在线', () => {
  const props = reactive({ row: row(), open: true, loading: true, error: '' })
  const view = mount(detail, props)
  try { assert.ok(find(view.root, 'ElSkeleton')); assert.ok(!text(view.root).includes(row().taskName)) } finally { view.close() }
  const failed = mount(detail, { open: true, loading: false, error: '记录不存在' })
  try { assert.equal(find(failed.root, 'ElAlert').props.title, '记录不存在') } finally { failed.close() }
  const unknown = mount(service, { data: { ...summary(), service: { ...summary().service, state: 'unknown' } }, stale: false, compact: true })
  try { assert.match(text(unknown.root),/状态未知/); assert.ok(!text(unknown.root).includes('服务在线')) } finally { unknown.close() }
})
