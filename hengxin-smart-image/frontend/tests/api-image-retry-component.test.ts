import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as types from '../src/types/api-image-edits'
import * as progress from '../src/views/hengxin/api-image-edits/retry-status'
import * as commands from '../src/views/hengxin/api-image-edits/item-command'
import { ApiError } from '../src/api/hengxin/http'
import { identity } from '../src/api/hengxin/identity'

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
const all = (n: Node): Node[] => [n, ...n.children.flatMap(all)]
const text = (n: Node): string => n.text + n.children.map(text).join('')
const simple = (name: string) => Vue.defineComponent({ setup(_p, { attrs, slots }) { return () => Vue.h(name, attrs, slots.default?.()) } })
const calls: { task: string; item: string; key: string }[] = []
let fail: 'unknown' | 'rejected' | '' = '', sequence = 0
const apiImages = {
  retryItem: async (task: string, item: string, key: string) => {
    calls.push({ task, item, key })
    if (fail) throw new ApiError('UPSTREAM_DETAIL', 'secret raw response', fail === 'unknown' ? 503 : 409)
    return { taskId: task }
  },
  download: async () => { throw new ApiError('DOWNLOAD', 'secret storage response', 502) },
  zip: async () => { throw new ApiError('DOWNLOAD', 'secret archive response', 502) }
}
const dependencies: Record<string, unknown> = {
  vue: Vue, '@/api/api-image-edits': { apiImages }, '@/types/api-image-edits': types,
  './retry-status': progress, './item-command': commands, '@/api/hengxin/identity': { identity },
  '@/store/modules/user': { useUserStore: () => ({ getUserInfo: { userId: 'retry-component' } }) }
}
function compile(name: string) {
  const source = readFileSync(new URL(`../src/views/hengxin/api-image-edits/${name}.vue`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: name, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((key: string) => {
    if (key in dependencies) return dependencies[key]
    if (key.endsWith('.vue')) return { default: simple(key) }
    throw new Error(key)
  }, module, module.exports)
  return module.exports.default
}
const detail = compile('RealTaskDetail')
const picture = { fileId: 'saved-image', url: '/saved.png', name: 'saved.png' }
const item = (state: types.ApiItemState, id = state): types.ApiItem => ({
  id, position: 1, state, source: picture, retries: 0, nextAttemptAt: null, error: 'secret generation response',
  result: state === 'succeeded' ? picture : null, currentVersion: state === 'succeeded' ? 1 : null,
  versions: [], revision: null
})
function mount(items: types.ApiItem[], status: types.ApiTaskState = 'running') {
  calls.length = 0; fail = ''
  const task: types.ApiTask = { id: `retry-ui-${++sequence}`, name: '任务', prompt: '提示词', created: '2026-10-20',
    operator: '用户', status, items, material: picture, batch: { current: 1, total: 1, running: 1 },
    error: 'secret task response', events: ['secret event response'], metrics: { requestCount: 8, retryCount: 7, elapsedSeconds: 20 } }
  const props = Vue.reactive({ modelValue: true, task, loading: false, error: '', actionError: '', busy: false, retryPending: false,
    channelBlocked: false, channel: { enabled: true, paused: false, reason: null }, onRefresh: () => { refreshes++ }, onRetry: (id: string) => batch.push(id) })
  let refreshes = 0
  const batch: string[] = [], root = node('root')
  const app = renderer.createApp({ render: () => Vue.h(detail, props) })
  for (const name of ['ElDrawer', 'ElButton', 'ElAlert', 'ElSkeleton', 'ElTag', 'ElCard', 'ElProgress', 'ElCollapse', 'ElCollapseItem']) app.component(name, simple(name))
  app.mount(root)
  return { props, root, batch, refreshes: () => refreshes, close: () => app.unmount() }
}
const buttons = (root: Node) => all(root).filter(n => n.tag === 'ElButton')
const button = (root: Node, label: string) => { const found = buttons(root).find(n => text(n) === label); assert.ok(found, label); return found }
const click = async (n: Node) => { assert.equal(!!n.props.disabled, false); await (n.props.onClick as () => Promise<void>)(); await Vue.nextTick() }

test('混合任务仅失败单张可重试，成功结果保留，未知和在途不出现新重试入口', async () => {
  const view = mount([item('succeeded'), item('failed'), item('running'), item('uncertain'), item('collecting')])
  try {
    assert.equal(buttons(view.root).filter(n => text(n) === '重试这张').length, 1)
    assert.equal(buttons(view.root).some(n => text(n).startsWith('重试未完成')), false)
    assert.match(text(view.root), /1 张未完成可逐张重试/)
    assert.doesNotMatch(text(view.root), /secret|需核实|发送名额|网络尝试|处理记录/)
    assert.ok(all(view.root).some(n => n.tag === './ApiResultPicture.vue' && (n.props.item as types.ApiItem).result?.fileId === picture.fileId))
    await click(button(view.root, '重试这张'))
    assert.equal(calls.length, 1); assert.equal(calls[0].item, 'failed'); assert.equal(view.refreshes(), 1)
  } finally { view.close() }
})

test('单张重试未知响应使用原键确认，通道暂停仍可确认，明确拒绝可重新尝试', async () => {
  const view = mount([item('failed')], 'failed')
  try {
    fail = 'unknown'; await click(button(view.root, '重试这张'))
    assert.match(text(view.root), /操作未完成，请再试一次/)
    assert.doesNotMatch(text(view.root), /secret/)
    view.props.channelBlocked = true; await Vue.nextTick()
    fail = ''; await click(button(view.root, '重试这张'))
    assert.equal(calls[0].key, calls[1].key)
    view.props.channelBlocked = false; await Vue.nextTick()
    fail = 'rejected'; await click(button(view.root, '重试这张'))
    assert.match(text(view.root), /操作未完成，请再试一次/)
    assert.equal(!!button(view.root, '重试这张').props.disabled, false)
    assert.notEqual(calls[1].key, calls[2].key)
  } finally { view.close() }
})

test('批量终态重试受原门槛保护，未知批量提交期间不允许新单图请求', async () => {
  const view = mount([item('failed'), item('failed', 'second')], 'failed')
  try {
    await click(button(view.root, '重试未完成的 2 张')); assert.deepEqual(view.batch, [view.props.task.id])
    view.props.retryPending = true; view.props.channelBlocked = true; await Vue.nextTick()
    assert.equal(!!button(view.root, '重试这张').props.disabled, true)
    await click(button(view.root, '重试未完成的 2 张')); assert.equal(view.batch.length, 2)
    view.props.retryPending = false; view.props.task.cliActivity = 'running'; await Vue.nextTick()
    assert.equal(buttons(view.root).some(n => text(n).startsWith('重试未完成')), false)
    view.props.task.cliActivity = 'idle'; view.props.task.status = 'uncertain'; await Vue.nextTick()
    assert.equal(buttons(view.root).some(n => text(n).startsWith('重试未完成')), false)
  } finally { view.close() }
})

test('下载失败保留成功状态并提示重试下载，不暴露内部响应', async () => {
  const view = mount([item('succeeded')], 'succeeded')
  try {
    await click(button(view.root, '下载图片'))
    assert.ok(all(view.root).some(n => n.tag === 'ElAlert' && n.props.title === '下载失败，请点击下载重试。'))
    assert.equal(view.props.task.items[0].state, 'succeeded')
    assert.equal(buttons(view.root).some(n => text(n) === '重试这张'), false)
    assert.doesNotMatch(text(view.root), /secret/)
  } finally { view.close() }
})
