import * as apiTypes from '../src/types/api-image-edits'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import { createApiImageClient } from '../src/api/api-image-edits'
import { picture as validatePicture } from '../src/api/api-image-edits-validate'
import type { ApiPicture, ApiTask } from '../src/types/api-image-edits'

const original = { fileId: 'original', name: 'original.jpg', url: '/original.jpg', width: 790, height: 1500 }
const pictures: ApiPicture[] = [
  { fileId: 'old', name: 'old.jpg', url: '/old.jpg' },
  { fileId: 'upstream', name: 'upstream.jpg', url: '/upstream.jpg', width: 800, height: 1520 },
  { fileId: 'final', name: 'final.png', url: '/final.png', width: 790, height: 1500 }
]
function fixture(): ApiTask {
  return structuredClone({ id: 'task', name: '任务', prompt: '替换屏幕', created: '2026-09-29', status: 'succeeded', operator: '测试',
    batch: { current: 1, total: 1, running: 0 }, material: original, events: [], error: null,
    metrics: { requestCount: 3, retryCount: 0, elapsedSeconds: 10 },
    items: [{ id: 'item', position: 1, source: original, result: pictures[2], currentVersion: 3, state: 'succeeded',
      retries: 0, nextAttemptAt: null, error: null, revision: null,
      versions: pictures.map((picture, index) => ({ number: index + 1, picture, created: '2026-09-29', operator: '测试', text: '', annotation: null, baseVersion: null })) }]
  })
}
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } })

test('真实客户端保留原图/当前/历史宽高，旧文件缺失尺寸仍能读取；无需另取图片', async () => {
  const calls: string[] = []
  const api = createApiImageClient('/api/v1', async url => { calls.push(String(url)); return json(fixture()) })
  const task = await api.task('task'), item = task.items[0]
  assert.deepEqual([item.source?.width, item.source?.height], [790, 1500])
  assert.deepEqual([item.result?.width, item.result?.height], [790, 1500])
  assert.deepEqual(item.versions.map(v => [v.picture.width, v.picture.height]), [[undefined, undefined], [800, 1520], [790, 1500]])
  assert.deepEqual(calls, ['/api/v1/api-image-edits/tasks/task'])
})

test('可选宽高仅接受正安全整数，错误值回退未知，图片基础契约依然严格', async () => {
  for (const value of [null, 0, -1, 1.5, '790', true, {}, [], Number.MAX_SAFE_INTEGER + 1, Infinity, NaN]) {
    for (const key of ['width', 'height']) {
      const picture: Record<string, unknown> = { ...original, [key]: value }
      assert.equal(validatePicture(picture), true)
      assert.equal(picture[key], undefined)
    }
  }
  assert.equal(validatePicture({ ...original, url: '' }), false)
  const body = fixture()
  const broken = body.items[0].versions[1].picture as unknown as Record<string, unknown>
  broken.width = '800'; broken.height = -1
  const api = createApiImageClient('/api/v1', async () => json(body))
  const old = (await api.task('task')).items[0].versions[1].picture
  assert.equal(old.width, undefined); assert.equal(old.height, undefined)
  const upload = createApiImageClient('/api/v1', async () => json(original))
  assert.deepEqual(await upload.upload(new File(['png'], 'a.png')), original)
})

// 编译并渲染真实 SFC。仅 Element Plus、图片预览与宿主 DOM 用轻量替身，
// 尺寸计算、模板、版本选择及响应式更新均执行生产代码。
interface Node { tag: string; text: string; props: Record<string, unknown>; children: Node[]; parent: Node | null }
const node = (tag: string, text = ''): Node => ({ tag, text, props: {}, children: [], parent: null })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: tag => node(tag), createText: text => node('#text', text), createComment: () => node('#comment'),
  insert(child, parent, anchor) {
    if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1)
    child.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, child)
  },
  remove(child) { child.parent?.children.splice(child.parent.children.indexOf(child), 1); child.parent = null },
  setText(child, text) { child.text = text }, setElementText(child, text) { child.children = []; child.text = text },
  parentNode: child => child.parent,
  nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp(child, key, _old, value) { child.props[key] = value }
})
const passthrough = Vue.defineComponent({ setup(_props, { slots }) { return () => Vue.h('div', {}, [slots.default?.(), slots.footer?.()]) } })
const preview = Vue.defineComponent({ props: ['picture'], setup(props) { return () => Vue.h('img', { src: props.picture.url }) } })
const operation = { state: Vue.reactive({ pending: null, busy: false, error: '' }) }
const dependencies: Record<string, unknown> = {
  vue: Vue,
  '@/types/api-image-edits': apiTypes,
  'element-plus': { ElMessage: {}, ElMessageBox: {} },
  '@/store/modules/user': { useUserStore: () => ({ getUserInfo: { userId: 'test-user' } }) },
  '@/api/api-image-edits': { apiImages: {}, errorText: String },
  './item-command': { itemCommand: () => operation, friendlyTime: String, saveBlob() {} },
  '../components/PicturePreview.vue': { default: preview }
}
function compile(name: string) {
  const source = readFileSync(new URL(`../src/views/hengxin/api-image-edits/${name}.vue`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: name, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((name: string) => {
    if (name in dependencies) return dependencies[name]
    throw new Error(`unexpected dependency: ${name}`)
  }, module, module.exports)
  return module.exports.default
}
const dimensions = compile('PictureDimensions')
dependencies['./PictureDimensions.vue'] = { default: dimensions }
const comparison = compile('SourceComparison'), history = compile('RealVersionDialog')
function mount(component: Vue.Component, initial: Record<string, unknown>) {
  const props = Vue.reactive(initial), root = node('root')
  const app = renderer.createApp({ render: () => Vue.h(component, props) })
  for (const name of ['ElDialog', 'ElTag', 'ElButton', 'ElEmpty', 'ElAlert']) app.component(name, passthrough)
  app.mount(root)
  return { root, props, unmount: () => app.unmount() }
}
const text = (root: Node): string => root.text + root.children.map(text).join('')
const all = (root: Node): Node[] => [root, ...root.children.flatMap(all)]
const sizes = (root: Node) => all(root).filter(n => n.props.class === 'picture-dimensions').map(text)

test('宽或高任一不一致即提示；缺一边、损坏尺寸或未知原图不误报', async () => {
  const view = mount(dimensions, { source: original, picture: original })
  try {
    for (const [width, height, label, warning] of [
      [800, 1500, '800 × 1500 px', true], [790, 1520, '790 × 1520 px', true],
      [790, undefined, '尺寸未知', false], [undefined, 1500, '尺寸未知', false],
      ['790', 1500, '尺寸未知', false], [790, -1, '尺寸未知', false],
      [Infinity, 1500, '尺寸未知', false], [790.5, 1500, '尺寸未知', false]
    ]) {
      view.props.picture = { ...original, width, height }; await Vue.nextTick()
      assert.deepEqual(sizes(view.root), [label])
      assert.equal(text(view.root).includes('尺寸不一致'), warning)
    }
    view.props.picture = pictures[1]; view.props.source = pictures[0]; await Vue.nextTick()
    assert.deepEqual(sizes(view.root), ['800 × 1520 px'])
    assert.doesNotMatch(text(view.root), /尺寸不一致/)
  } finally { view.unmount() }
})

test('真实对照SFC显示文件尺寸，切换图片/版本立即更新，警示不拦截图片或关闭', async () => {
  const view = mount(comparison, { modelValue: true, position: 1, source: original, result: pictures[2], version: 3 })
  try {
    assert.deepEqual(sizes(view.root), ['790 × 1500 px', '790 × 1500 px'])
    assert.match(text(view.root), /V3/); assert.doesNotMatch(text(view.root), /尺寸不一致/)
    view.props.result = pictures[1]; view.props.version = 2; await Vue.nextTick()
    assert.deepEqual(sizes(view.root), ['790 × 1500 px', '800 × 1520 px'])
    assert.match(text(view.root), /V2/); assert.match(text(view.root), /尺寸不一致/)
    assert.equal(all(view.root).find(n => n.props.src === '/upstream.jpg')?.tag, 'img')
    assert.match(text(view.root), /关闭对照/)
    view.props.result = pictures[0]; view.props.version = 1; await Vue.nextTick()
    assert.deepEqual(sizes(view.root), ['790 × 1500 px', '尺寸未知'])
    assert.doesNotMatch(text(view.root), /尺寸不一致/)
    view.props.source = null; view.props.result = null; await Vue.nextTick()
    assert.deepEqual(sizes(view.root), ['尺寸未知', '尺寸未知'])
    assert.equal(all(view.root).filter(n => n.tag === 'img').length, 0)
  } finally { view.unmount() }
})

test('历史版本真实选择事件从同尺寸到不同尺寸及未知；当前结果与原图保持正确映射', async () => {
  const api = createApiImageClient('/api/v1', async () => json(fixture()))
  const task = await api.task('task')
  const view = mount(history, { modelValue: true, task, itemId: 'item' })
  try {
    assert.deepEqual(sizes(view.root), ['790 × 1500 px', '790 × 1500 px'])
    const choose = async (number: number) => {
      const button = all(view.root).find(n => n.tag === 'button' && text(n).startsWith(`V${number}`))!
      assert.equal(button.props.disabled, false)
      ;(button.props.onClick as () => void)(); await Vue.nextTick()
    }
    await choose(2)
    assert.deepEqual(sizes(view.root), ['800 × 1520 px', '790 × 1500 px'])
    assert.match(text(view.root), /选中版本 · V2/); assert.match(text(view.root), /尺寸不一致/)
    assert.ok(all(view.root).some(n => n.props.src === '/upstream.jpg'))
    await choose(1)
    assert.deepEqual(sizes(view.root), ['尺寸未知', '790 × 1500 px'])
    assert.doesNotMatch(text(view.root), /尺寸不一致/)
    task.items[0].result = pictures[1]; task.items[0].currentVersion = 2
    view.props.task = structuredClone(task); await Vue.nextTick()
    assert.deepEqual(sizes(view.root), ['尺寸未知', '800 × 1520 px'])
    assert.match(text(view.root), /当前结果 · V2/); assert.match(text(view.root), /尺寸不一致/)
  } finally { view.unmount() }
})
