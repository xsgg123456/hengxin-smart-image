import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as helpers from '../src/views/hengxin/components/upload-interaction'

// 执行真实 SFC setup 与生命周期；宿主仅替代 DOM，不复制组件事件逻辑。
const source = readFileSync(new URL('../src/views/hengxin/components/UploadInteraction.vue', import.meta.url), 'utf8')
const compiled = compileScript(parse(source).descriptor, { id: 'upload-test' }).content
const code = ts.transpileModule(compiled, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
interface Surface { contains(value: unknown): boolean; focus(): void }
interface Handlers {
  surface: Vue.Ref<Surface | undefined>
  dragging: Vue.Ref<boolean>
  paste(event: ClipboardEvent): void
  drop(event: DragEvent): void
  pasteButton(): Promise<void>
}
const module = { exports: {} as { default: { setup(props: object, context: object): Handlers } } }
new Function('require', 'module', 'exports', code)((name: string) => name === 'vue' ? Vue : helpers, module, module.exports)
const renderer = Vue.createRenderer<object, object>({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {},
  setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}
})
class FakeElement {
  constructor(public text = false) {}
  closest() { return this.text ? this : null }
}
Object.defineProperty(globalThis, 'Element', { configurable: true, value: FakeElement })
const doc = { activeElement: null as unknown }
Object.defineProperty(globalThis, 'document', { configurable: true, value: doc })
function mount() {
  let handlers!: Handlers
  const props = Vue.reactive({ disabled: false }), events: { kind: string; value: unknown }[] = []
  const app = renderer.createApp(Vue.defineComponent({ setup() {
    handlers = module.exports.default.setup(props, { expose() {}, emit: (kind: string, value: unknown) => events.push({ kind, value }) })
    return () => Vue.h('div')
  } }))
  app.mount({})
  const surface = { contains: (value: unknown) => value === surface, focus: () => { doc.activeElement = surface } }
  handlers.surface.value = surface
  return { handlers, props, events, surface, unmount: () => app.unmount() }
}
const png = new File(['png'], 'a.png', { type: 'image/png' })
function event(types = ['Files'], target = new FakeElement()) {
  let prevented = false, stopped = false
  return { target, clipboardData: { files: [png] }, dataTransfer: { types, files: [png] },
    preventDefault() { prevented = true }, stopPropagation() { stopped = true },
    get prevented() { return prevented }, get stopped() { return stopped } }
}
test('原生粘贴只投递聚焦上传区，文字输入与未聚焦区不截取', () => {
  const m = mount()
  try {
    const first = event(); doc.activeElement = null; m.handlers.paste(first as unknown as ClipboardEvent)
    assert.equal(m.events.length, 0); assert.equal(first.prevented, false)
    doc.activeElement = m.surface
    const text = event([], new FakeElement(true)); m.handlers.paste(text as unknown as ClipboardEvent)
    assert.equal(m.events.length, 0); assert.equal(text.prevented, false)
    const image = event(); m.handlers.paste(image as unknown as ClipboardEvent)
    assert.deepEqual(m.events, [{ kind: 'files', value: [png] }]); assert.equal(image.prevented, true)
    m.props.disabled = true; m.handlers.paste(event() as unknown as ClipboardEvent)
    assert.equal(m.events.length, 1)
  } finally { m.unmount() }
})
test('仅外部文件拖入触发上传，内部排序保持原事件，禁用时拦截但不投递', () => {
  const m = mount()
  try {
    const sorting = event(['text/plain']); m.handlers.drop(sorting as unknown as DragEvent)
    assert.equal(sorting.stopped, false); assert.equal(m.events.length, 0)
    m.handlers.drop(event() as unknown as DragEvent); assert.equal(m.events.length, 1)
    m.props.disabled = true
    const disabled = event(); m.handlers.drop(disabled as unknown as DragEvent)
    assert.equal(disabled.prevented, true); assert.equal(m.events.length, 1)
  } finally { m.unmount() }
})
test('异步剪贴板读取正常投递；期间禁用、禁用后恢复或卸载均不投递', async () => {
  for (const change of ['none', 'disable', 'reenable', 'unmount']) {
    const m = mount()
    let finish!: (items: unknown[]) => void
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: { read: () => new Promise(resolve => { finish = resolve }) } } })
    const pending = m.handlers.pasteButton()
    if (change === 'disable' || change === 'reenable') m.props.disabled = true
    if (change === 'reenable') m.props.disabled = false
    if (change === 'unmount') m.unmount()
    finish([{ types: ['image/png'], getType: async () => png }]); await pending
    assert.equal(m.events.length, change === 'none' ? 1 : 0, change)
    if (change !== 'unmount') m.unmount()
  }
})
test('剪贴板权限拒绝显示可操作提示，读取中卸载后不回写错误', async () => {
  for (const unmount of [false, true]) {
    const m = mount(); let fail!: (reason: Error) => void
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: { read: () => new Promise((_resolve, reject) => { fail = reject }) } } })
    const pending = m.handlers.pasteButton()
    if (unmount) m.unmount()
    fail(new Error('denied')); await pending
    assert.deepEqual(m.events, unmount ? [] : [{ kind: 'error', value: helpers.clipboardHint }])
    if (!unmount) m.unmount()
  }
})
