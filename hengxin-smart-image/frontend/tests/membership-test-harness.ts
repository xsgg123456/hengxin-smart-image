import * as BeijingTime from '../src/utils/beijing-time'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
export interface Node { tag: string; text: string; props: Record<string, unknown>; children: Node[]; parent: Node | null }
const node = (tag: string, text = ''): Node => ({ tag, text, props: {}, children: [], parent: null })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: tag => node(tag), createText: text => node('#text', text), createComment: () => node('#comment'),
  insert(child, parent, anchor) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; parent.children.splice(i < 0 ? parent.children.length : i, 0, child) },
  remove(child) { child.parent?.children.splice(child.parent.children.indexOf(child), 1); child.parent = null },
  setText(child, text) { child.text = text }, setElementText(child, text) { child.children = []; child.text = text },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp(child, key, _old, value) { child.props[key] = value }
})
export const simple = (tag: string) => Vue.defineComponent({ setup(_p, { attrs, slots }) { return () => Vue.h(tag, attrs, [Vue.h('content', slots.default?.() || []), Vue.h('footer', slots.footer?.() || [])]) } })
export const table = Vue.defineComponent({ props: ['data'], setup(p, { attrs, slots }) { return () => Vue.h('ArtTable', { ...attrs, data: p.data }, (p.data as unknown[]).flatMap(row => Object.values(slots).flatMap(slot => slot?.({ row }) || []))) } })
export function compile(path: string, deps: Record<string, unknown>) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: path, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((name: string) => { if (name === 'vue') return Vue; if (name === '@/utils/beijing-time') return BeijingTime; if (name in deps) return deps[name]; throw new Error(`Unexpected test dependency ${name}`) }, module, module.exports)
  return module.exports.default
}
export function mount(component: Vue.Component, props = {}) {
  const root = node('root'), app = renderer.createApp({ render: () => Vue.h(component, props) })
  for (const name of ['ElAlert', 'ElButton', 'ElCard', 'ElDialog', 'ElForm', 'ElFormItem', 'ElInput', 'ElOption', 'ElPagination', 'ElSelect', 'ElSwitch', 'ElTabs', 'ElTabPane', 'ElTag', 'ElRadioGroup', 'ElRadio', 'ElRadioButton']) app.component(name, simple(name))
  app.mount(root); return { root, close: () => app.unmount() }
}
export const all = (n: Node): Node[] => [n, ...n.children.flatMap(all)]
export const text = (n: Node): string => n.text + n.children.map(text).join('')
export function find(root: Node, tag: string, label?: string) { const found = all(root).find(n => n.tag === tag && (!label || n.props['aria-label'] === label)); assert.ok(found, `${tag} ${label}`); return found }
export const update = (n: Node, v: unknown) => (n.props['onUpdate:modelValue'] as (v: unknown) => void)(v)
export const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
export function click(root: Node, label: string) { const found = all(root).find(n => n.tag === 'ElButton' && text(n) === label); assert.ok(found, label); (found.props.onClick as () => void)() }
