import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import { downloadAttachment } from '../src/api/overseas/attachment-download'
import { IdentityError } from '../src/api/identity/request'
interface N { tag: string; children: N[]; parent: N | null; props: Record<string, unknown>; text: string }
const node = (text = '', tag = ''): N => ({ tag, text, children: [], parent: null, props: {} })
const renderer = Vue.createRenderer<N, N>({ createElement: t => node('', t), createText: node, createComment: node, insert(c, p) { c.parent = p; p.children.push(c) }, remove(c) { if (c.parent) c.parent.children.splice(c.parent.children.indexOf(c), 1) }, parentNode: c => c.parent, nextSibling: () => null, patchProp: (e, k, _o, v) => { e.props[k] = v }, setText: (e, t) => { e.text = t }, setElementText: (e, t) => { e.text = t } })
const flatten = (e: N): N[] => [e, ...e.children.flatMap(flatten)], text = (e: N): string => e.text + e.children.map(text).join('')
const flush = async () => { for (let i = 0; i < 10; i++) { await Promise.resolve(); await Vue.nextTick() } }
function mount(fetcher: typeof fetch) {
  const descriptor = parse(readFileSync(new URL('../src/views/overseas/AttachmentDownload.vue', import.meta.url), 'utf8')).descriptor
  const code = ts.transpileModule(compileScript(descriptor, { id: 'download-test', inlineTemplate: true }).content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as { default: Vue.Component } }, errors: unknown[] = []
  const require = (path: string) => path === 'vue' ? Vue : path.endsWith('/request') ? { IdentityError } : { downloadAttachment: (url: string, name: string, signal: AbortSignal) => downloadAttachment(url, name, signal, fetcher) }
  new Function('require', 'module', 'exports', code)(require, module, module.exports)
  const app = renderer.createApp(module.exports.default, { url: '/api/overseas/v1/materials/m/content', name: '材料.pdf', onFailure: (e: unknown) => errors.push(e) })
  app.component('ElButton', Vue.defineComponent({ setup(_, { attrs, slots }) { return () => Vue.h('button', attrs, slots.default?.()) } }))
  const root = node(); app.mount(root)
  return { app, root, errors, click: async (label: string) => { const button = flatten(root).find(e => e.tag === 'button' && text(e) === label); assert.ok(button); (button.props.onClick as () => void)(); await flush() } }
}
test('实际下载组件展示权限失败并可重试，不显示完成', async () => {
  for (const status of [401, 403]) {
    const view = mount(async () => new Response(null, { status }))
    await view.click('下载原文件')
    assert.match(text(view.root), /身份已失效|暂无权限下载此附件/); assert.equal(view.errors.length, 1)
    assert.doesNotMatch(text(view.root), /已发起|下载完成/)
    await view.click('下载原文件'); assert.equal(view.errors.length, 2); view.app.unmount()
  }
})
test('附件503、404和网络失败只在卡片显示，重试成功保留父页面', async () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  let clicks = 0
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { body: { appendChild() {} }, createElement: () => ({ href: '', download: '', click() { clicks++ }, remove() {} }) } })
  try {
    for (const status of [503, 404, 0]) {
      let calls = 0
      const view = mount(async () => { if (++calls > 1) return new Response(null); if (!status) throw Error('offline'); return new Response(null, { status }) })
      await view.click('下载原文件')
      assert.match(text(view.root), /无法下载|不存在|连接失败/); assert.equal(view.errors.length, 0)
      await view.click('下载原文件')
      assert.equal(calls, 2); assert.equal(view.errors.length, 0); assert.match(text(view.root), /已发起下载/)
      assert.doesNotMatch(text(view.root), /无法下载|不存在|连接失败/); view.app.unmount()
    }
    assert.equal(clicks, 3)
  } finally { if (original) Object.defineProperty(globalThis, 'document', original); else Reflect.deleteProperty(globalThis, 'document') }
})
test('实际下载组件取消和卸载中断HEAD，迟到响应不创建下载', async () => {
  for (const mode of ['cancel', 'unmount']) {
    let finish!: (response: Response) => void, signal: AbortSignal | undefined
    const view = mount(async (_url, options) => { signal = options?.signal as AbortSignal; return new Promise<Response>(resolve => { finish = resolve }) })
    await view.click('下载原文件')
    assert.match(text(view.root), /取消检查/)
    if (mode === 'cancel') await view.click('取消检查'); else view.app.unmount()
    assert.ok(signal?.aborted)
    finish(new Response(null)); await flush(); assert.equal(view.errors.length, 0)
    if (mode === 'cancel') { assert.doesNotMatch(text(view.root), /已发起/); view.app.unmount() }
  }
})
