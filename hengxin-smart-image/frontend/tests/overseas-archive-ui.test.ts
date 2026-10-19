import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as BeijingTime from '../src/utils/beijing-time'
import * as Archives from '../src/api/overseas/archives'
import { IdentityError } from '../src/api/identity/request'
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
const picture = { id: 'p', name: '真实图片.png', sku: 'SKU-A', width: 10, height: 10, contentType: 'image/png', sizeBytes: 12, url: Archives.archivePictureUrl('a', 'p') }
const event = { id: 'e', actorId: 'actual', actorName: '实际确认者', at: '2026-10-19T01:02:03Z', pictures: [{ id: 'p', name: picture.name, sku: picture.sku }] }
const fixture: Archives.ArchiveDetail = { id: 'a', taskId: 'task', sourceDeleted: false, productName: '真实品名', brand: '真实品牌', platform: 'Amazon', skus: [{ code: 'SKU-A' }], pictureCount: 1, createdAt: '2026-01-01T00:00:00Z', pictures: [picture], cover: picture, latestArchive: event, archiveHistory: [event], historyIncomplete: false }
let result = structuredClone(fixture), rejected = false, listEmpty = false
const requestedPages: number[] = []
const api = { get: async () => { if (rejected) throw new IdentityError(403, '暂无权限'); return structuredClone(result) }, list: async (query: { page: number }) => { requestedPages.push(query.page); return { items: listEmpty ? [] : [structuredClone(result)], total: listEmpty ? 0 : 21, page: query.page, pageSize: 20 } } }
const simple = (name: string) => Vue.defineComponent({ name, setup(_p, { attrs, slots }) { return () => Vue.h(name, attrs, slots.default?.()) } })
const deps: Record<string, unknown> = {
  vue: Vue, 'vue-router': { useRouter: () => ({ push: () => undefined }) },
  '@/utils/beijing-time': BeijingTime, '@/api/identity/request': { IdentityError },
  '@/api/overseas/archives': { ...Archives, createArchivesApi: () => api }, '@/api/overseas/pictures': { saveBlob: () => undefined },
  './OverseasArchiveDelete.vue': { default: simple('Delete') }, './OverseasArchivePicture.vue': { default: simple('Picture') }, './OverseasArchiveViewer.vue': { default: simple('Viewer') }, './OverseasArchiveCover.vue': { default: simple('Cover') }
}
function compile(name: string) {
  const source = readFileSync(new URL(`../src/views/overseas/${name}.vue`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: name, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((key: string) => { if (key in deps) return deps[key]; throw new Error(`unexpected dependency ${key}`) }, module, module.exports)
  return module.exports.default
}
deps['./OverseasArchiveFields.vue'] = { default: compile('OverseasArchiveFields') }
const detail = compile('OverseasArchiveDetail')
deps['./OverseasArchiveDetail.vue'] = { default: detail }
const page = compile('OverseasArchivePage')
function mount(component: Vue.Component, props: Record<string, unknown>) {
  const root = node('root'), app = renderer.createApp({ render: () => Vue.h(component, props) })
  for (const name of ['ElDialog', 'ElButton', 'ElAlert', 'ElCard', 'ElInput', 'ElTag', 'ElEmpty', 'ElPagination']) app.component(name, simple(name))
  app.mount(root)
  return { root, close: () => app.unmount() }
}
const all = (n: Node): Node[] => [n, ...n.children.flatMap(all)]
const text = (n: Node): string => n.text + n.children.map(text).join('')
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }

test('正式成品卡片明确四字段，只有已归档状态，没有重复品牌标签', async () => {
  result = structuredClone(fixture); rejected = false
  const view = mount(page, { refresh: 0 })
  try {
    await flush()
    assert.deepEqual(all(view.root).filter(n => n.tag === 'dt').map(text), ['品名', '品牌', '平台', 'SKU', '归档人', '归档时间'])
    assert.deepEqual(all(view.root).filter(n => n.tag === 'ElTag').map(text), ['21 套归档', '已归档'])
    assert.match(text(view.root), /归档人实际确认者/)
    assert.match(text(view.root), /2026-10-19 09:02:03/)
    assert.doesNotMatch(text(view.root), /2026-01-01/)
  } finally { view.close() }
})

test('正式详情可展开实际操作历史、图片SKU及北京时区，未知记录明确提示', async () => {
  for (const known of [true, false]) {
    result = known ? structuredClone(fixture) : { ...fixture, latestArchive: null, archiveHistory: [], historyIncomplete: true }
    const view = mount(detail, { id: 'a', api })
    try {
      await flush()
      assert.deepEqual(all(view.root).filter(n => n.tag === 'dt').map(text), ['品名', '品牌', '平台', 'SKU', '归档人', '归档时间'])
      assert.ok(all(view.root).some(n => n.tag === 'details'))
      if (known) { assert.match(text(view.root), /实际确认者.*2026-10-19 09:02:03/); assert.match(text(view.root), /真实图片.png · SKU：SKU-A/) }
      else { assert.match(text(view.root), /历史记录未记录/); assert.doesNotMatch(text(view.root), /实际确认者/) }
    } finally { view.close() }
  }
})

test('详情权限失效不残留归档人与图片历史', async () => {
  result = structuredClone(fixture); rejected = false
  const view = mount(detail, { id: 'a', api })
  try {
    await flush(); assert.match(text(view.root), /实际确认者/)
    rejected = true
    const refresh = all(view.root).find(n => n.tag === 'ElButton' && text(n) === '刷新成品详情')!
    await (refresh.props.onClick as () => Promise<void>)(); await flush()
    assert.doesNotMatch(text(view.root), /实际确认者|真实图片.png/)
  } finally { view.close(); rejected = false }
})


test('删除最后一页最后一套后刷新总数并退回第一页；删除中不请求封面', async () => {
 result = structuredClone(fixture); rejected = false; listEmpty = false; requestedPages.length = 0
 const view = mount(page, {refresh: 0, capabilities: ['task.delete']})
 try {
  await flush()
  const pager = all(view.root).find(n => n.tag === 'ElPagination')!
  ;(pager.props.onCurrentChange as (page: number) => void)(2); await flush()
  const deletion = all(view.root).find(n => n.tag === 'Delete')!
  ;(deletion.props.onChanged as (value: unknown) => void)({archiveId: 'a', status: 'deleting', error: null}); await flush()
  assert.equal(all(view.root).some(n => n.tag === 'Cover'), false)
  assert.equal(all(view.root).find(n => n.tag === 'ElButton' && text(n) === '下载整套成品')?.props.disabled, true)
  listEmpty = true
  ;(deletion.props.onChanged as (value: unknown) => void)({archiveId: 'a', status: 'deleted', error: null}); await flush(); await flush()
  assert.deepEqual(requestedPages, [1,2,2,1]); assert.match(text(view.root), /0 套归档/)
 } finally {view.close(); listEmpty = false}
})
