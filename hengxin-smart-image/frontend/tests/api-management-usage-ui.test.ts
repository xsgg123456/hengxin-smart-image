import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import { useAdminQuery } from '../src/views/hengxin/admin/use-admin-query'
import { usageCategoryLabels } from '../src/api/api-management-usage-validate'
import type { ApiUsageQuery } from '../src/types/api-management-usage'
import { usageFixture } from './api-management-usage-fixture'
interface Node { tag: string; text: string; props: Record<string, unknown>; children: Node[]; parent: Node | null }
const node = (tag: string, text = ''): Node => ({ tag, text, props: {}, children: [], parent: null })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: tag => node(tag), createText: text => node('#text', text), createComment: () => node('#comment'),
  insert(child, parent, anchor) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; parent.children.splice(i < 0 ? parent.children.length : i, 0, child) },
  remove(child) { child.parent?.children.splice(child.parent.children.indexOf(child), 1); child.parent = null },
  setText(child, text) { child.text = text }, setElementText(child, text) { child.children = []; child.text = text },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp(child, key, _old, value) { child.props[key] = value }
})
const calls: ApiUsageQuery[] = [], navigation: unknown[] = []
let result = usageFixture(), fail = false, roles = ['super_admin']; let pending: Promise<void> | undefined
const deps: Record<string, unknown> = {
  vue: Vue, 'vue-router': { useRouter: () => ({ push: (q: unknown) => navigation.push(q) }) },
  '@/api/api-management-usage': { getApiUsage: async (q: ApiUsageQuery) => { calls.push({ ...q }); if (pending) await pending; if (fail) throw new Error('统计服务不可用'); return structuredClone(result) } },
  '@/api/api-management-usage-validate': { usageCategoryLabels },
  '@/store/modules/user': { useUserStore: () => ({ info: { roles } }) }, './use-admin-query': { useAdminQuery }
}
function compile(name: string) {
  const source = readFileSync(new URL(`../src/views/hengxin/admin/${name}.vue`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: name, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((key: string) => { if (key in deps) return deps[key]; throw new Error(`unexpected dependency ${key}`) }, module, module.exports)
  return module.exports.default
}
const detail = compile('ApiUsageDetail')
deps['./ApiUsageDetail.vue'] = { default: detail }
const usage = compile('ApiUsage')
const simple = (name: string) => Vue.defineComponent({ name, setup(_p, { attrs, slots }) { return () => Vue.h(name, attrs, slots.default?.()) } })
const table = Vue.defineComponent({ props: ['data'], setup(p, { attrs, slots }) { Vue.provide('rows', Vue.computed(() => p.data)); return () => Vue.h('ElTable', { ...attrs, data: p.data }, slots.default?.()) } })
const column = Vue.defineComponent({ setup(_p, { attrs, slots }) { const rows = Vue.inject<Vue.ComputedRef<unknown[]>>('rows')!; return () => Vue.h('ElTableColumn', attrs, rows.value.flatMap(row => slots.default?.({ row }) || [])) } })
function mount(component: Vue.Component, props = {}) {
  const root = node('root'), app = renderer.createApp({ render: () => Vue.h(component, props) })
  for (const name of ['ElAlert', 'ElButton', 'ElCard', 'ElDatePicker', 'ElDrawer', 'ElOption', 'ElPagination', 'ElSelect', 'ElSkeleton', 'ElTabPane', 'ElTabs', 'ElTag']) app.component(name, simple(name))
  app.component('ElTable', table); app.component('ElTableColumn', column); app.mount(root)
  return { root, close: () => app.unmount() }
}
const all = (n: Node): Node[] => [n, ...n.children.flatMap(all)]
const text = (n: Node): string => n.text + n.children.map(text).join('')
const find = (root: Node, tag: string, label?: string) => { const found = all(root).find(n => n.tag === tag && (!label || n.props['aria-label'] === label)); assert.ok(found, `${tag} ${label}`); return found }
const update = (n: Node, v: unknown) => (n.props['onUpdate:modelValue'] as (v: unknown) => void)(v)
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
const click = (root: Node, label: string) => { const n = all(root).find(n => n.tag === 'ElButton' && text(n) === label); assert.ok(n, label); (n.props.onClick as () => void)() }
function reset() { calls.length = 0; navigation.length = 0; result = usageFixture(); fail = false; roles = ['super_admin']; pending = undefined }

test('真实统计组件：分页不改变全量汇总、筛选显式提交、失败隐藏旧结果且可重试', async () => {
  reset(); const view = mount(usage)
  try {
    await Vue.nextTick(); await flush()
    assert.equal((find(view.root, 'ElTable').props.data as unknown[]).length, 8)
    const kpis = () => all(view.root).filter(n => n.props.class === 'hx-admin-kpis').map(text).join(''); const before = kpis()
    ;(find(view.root, 'ElPagination').props['onUpdate:currentPage'] as (v: number) => void)(2); await flush()
    assert.equal((find(view.root, 'ElTable').props.data as unknown[]).length, 2)
    assert.equal(kpis(), before); assert.equal(calls.length, 1)
    update(find(view.root, 'ElDatePicker'), ['2026-10-02', '2026-10-03'])
    update(find(view.root, 'ElSelect', '统计人员'), 'u1')
    update(find(view.root, 'ElSelect', '统计事件类型'), 'api_request')
    assert.equal(calls.length, 1)
    fail = true; click(view.root, '查询统计'); await flush()
    assert.deepEqual(calls.at(-1), { from: '2026-10-02', to: '2026-10-03', userId: 'u1', category: 'api_request', page: 1, pageSize: 1 })
    assert.equal(find(view.root, 'ElAlert').props.title, '统计服务不可用')
    assert.equal(all(view.root).some(n => n.tag === 'ElTable'), false)
    fail = false; click(view.root, '重试加载'); await flush(); assert.ok(find(view.root, 'ElTable'))
    assert.match(text(view.root), /仅按创建人过滤，不受日期与事件类型影响/); assert.match(text(view.root), /来源待核实版本 2（不计生成或采用）/)
    assert.match(text(view.root), /费用：未提供/)
  } finally { view.close() }
})
test('真实统计组件：个人视图不发送其他人员、空态保留真实零记录', async () => {
  reset(); roles = ['operator']; result.scope = 'personal'; result.rows = []; result.events = []; result.total = 0
  const view = mount(usage)
  try { await flush(); assert.equal(all(view.root).some(n => n.props['aria-label'] === '统计人员'), false); click(view.root, '查询统计'); await flush(); assert.equal(calls.at(-1)?.userId, undefined); assert.deepEqual(find(view.root, 'ElTable').props.data, []); assert.equal(find(view.root, 'ElTable').props['empty-text'], '此范围暂无统计记录') } finally { view.close() }
})
test('真实明细组件：未知归属独立查询，删除任务不跳转，事件分页与API任务跳转正确', async () => {
  reset(); const row = { ...result.rows[0]!, userId: null }
  const view = mount(detail, { row, category: 'cli_round' })
  try {
    await flush(); assert.equal(calls[0]?.unassigned, true); assert.equal(calls[0]?.userId, undefined)
    assert.equal(calls[0]?.from, row.date); assert.equal(calls[0]?.to, row.date); assert.equal(calls[0]?.category, 'cli_round')
    assert.match(text(view.root), /已删除/); assert.match(text(view.root), /历史归属未核实/)
    assert.equal(all(view.root).filter(n => n.tag === 'ElButton').length, 0)
    result.events[0]!.taskDeleted = false
    ;(find(view.root, 'ElPagination').props.onCurrentChange as (v: number) => void)(2); await flush()
    assert.equal(calls.at(-1)?.page, 2); click(view.root, '保留的历史任务')
    assert.deepEqual(navigation, [{ path: '/api-image-edits/records', query: { task: 't1' } }])
  } finally { view.close() }
})


test('真实统计组件：初次慢加载显式等待，不伪造个人范围或零数据', async () => {
  reset(); let finish!: () => void; pending = new Promise<void>(resolve => { finish = resolve })
  const view = mount(usage)
  try {
    await Vue.nextTick(); assert.ok(find(view.root, 'ElSkeleton'))
    assert.doesNotMatch(text(view.root), /个人/); assert.doesNotMatch(text(view.root), /当前原图库存/)
    finish(); await flush(); update(find(view.root, 'ElTabs'), 'execution'); await flush()
    assert.match(text(view.root), /CLI 真实启动/); assert.match(text(view.root), /启动证据不足 1/)
    assert.match(text(view.root), /API 请求成功率 50.0%/); assert.match(text(view.root), /未知 2/)
  } finally { finish(); pending = undefined; view.close() }
})
