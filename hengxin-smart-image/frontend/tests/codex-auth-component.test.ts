import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as contract from '../src/api/codex-auth'
import * as accountHook from '../src/views/codex-auth/use-account'
import * as authorizationHook from '../src/views/codex-auth/use-authorization'

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
const text = (n: Node): string => n.text + String(n.props.title || '') + n.children.map(text).join('')
const simple = (name: string) => Vue.defineComponent({ setup(_p, { attrs, slots }) { return () => name === 'ElDialog' && !(attrs.modelValue ?? attrs['model-value']) ? null : Vue.h(name, attrs, [slots.default?.(), slots.footer?.()]) } })
const dependencies: Record<string, unknown> = { vue: Vue, 'element-plus': { ElMessage: { info() {} } }, '../../api/codex-auth': contract, './use-account': accountHook, './use-authorization': authorizationHook, './style.css': {} }
function compile(name: string) {
  const source = readFileSync(new URL(`../src/views/codex-auth/${name}.vue`, import.meta.url), 'utf8')
  const content = compileScript(parse(source).descriptor, { id: name, inlineTemplate: true }).content
  const code = ts.transpileModule(content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  new Function('require', 'module', 'exports', code)((key: string) => {
    if (key in dependencies) return dependencies[key]
    if (key === './AuthorizationDialog.vue') return { default: compile('AuthorizationDialog') }
    throw new Error(key)
  }, module, module.exports)
  return module.exports.default
}
function mount(component: Vue.Component, props: Record<string, unknown>) {
  const root = node('root'), app = renderer.createApp({ render: () => Vue.h(component, props) })
  for (const name of ['ElDialog', 'ElButton', 'ElAlert', 'ElSkeleton', 'ElTag', 'ElCard', 'ElEmpty', 'ElTable', 'ElTableColumn', 'ElCheckbox']) app.component(name, simple(name))
  app.mount(root); return { root, close: () => app.unmount() }
}
const flush = async () => { for (let i = 0; i < 15; i++) await Promise.resolve(); await Vue.nextTick() }
const button = (root: Node, label: string) => { const found = all(root).find(n => n.tag === 'ElButton' && text(n) === label); assert.ok(found, label); return found }
const click = async (n: Node) => { assert.equal(!!n.props.disabled, false); await (n.props.onClick as () => Promise<void>)(); await flush() }
const account: contract.Account = { status: 'unchecked', email: '', workspace: 'workspace-id', checked: '', updated: '', audit: [], revision: 2, checking: false }
const candidate: contract.Authorization = { id: 'candidate', step: 'waiting', userCode: 'REAL-CODE', verificationUrl: 'https://auth.openai.com/codex/device', expiresAt: Date.now() / 1000 + 60, candidateEmail: '', candidateWorkspace: '', different: false, message: '' }
function api(overrides: Partial<contract.CodexAuthApi> = {}): contract.CodexAuthApi {
  return { get: async () => account, check: async () => ({ ...account, checking: false, status: 'ready' }), start: async () => candidate, poll: async () => candidate, retry: async () => ({ ...candidate, step: 'checking' }), activate: async () => ({ ...account, status: 'ready' }), cancel: async () => ({ ok: true }), remove: async () => ({ ...account, status: 'empty' }), ...overrides }
}

test('正式页面无邮箱仍可真实检测，未检测状态和真实工作区完整显示', async () => {
  let checked = 0
  const view = mount(compile('AccountPage'), { side: 'domestic', adapter: api({ check: async () => { checked++; return { ...account, status: 'ready' } } }) })
  try {
    await flush(); assert.match(text(view.root), /尚未检测/); assert.match(text(view.root), /workspace-id/)
    assert.doesNotMatch(text(view.root), /演示|DEMO|个人工作区/)
    await click(button(view.root, '检测连接')); assert.equal(checked, 1); assert.match(text(view.root), /可用/)
  } finally { view.close() }
})
test('授权启动失败没有候选时提供重新获取，不把用户困在重试检测', async () => {
  const view = mount(compile('AuthorizationDialog'), { side: 'overseas', intent: 'renew', current: account, api: api({ start: async () => ({ ...candidate, step: 'failed', message: '登录失败' }) }) })
  try {
    await flush(); assert.ok(button(view.root, '重新获取授权码'))
    assert.equal(all(view.root).some(n => n.tag === 'ElButton' && text(n) === '重试检测'), false)
    assert.doesNotMatch(text(view.root), /模拟|DEMO|个人工作区/)
  } finally { view.close() }
})
test('实际确认按钮遵循服务端different而非邮箱，勾选后才能启用', async () => {
  let enabled = 0
  const view = mount(compile('AuthorizationDialog'), { side: 'overseas', intent: 'replace', current: account, api: api({ start: async () => ({ ...candidate, step: 'verified', candidateEmail: account.email, candidateWorkspace: 'other-workspace', different: true }), activate: async (_id, acknowledged) => { assert.equal(acknowledged, true); enabled++; return account } }) })
  try {
    await flush(); assert.equal(button(view.root, '确认更换并启用').props.disabled, true)
    const checkbox = all(view.root).find(n => n.tag === 'ElCheckbox')!
    assert.ok(checkbox); (checkbox.props['onUpdate:modelValue'] as (value: boolean) => void)(true); await flush()
    await click(button(view.root, '确认更换并启用')); assert.equal(enabled, 1)
  } finally { view.close() }
})
test('移除失败仍显示原配置和错误；取消后可重新读取恢复', async () => {
  const view = mount(compile('AccountPage'), { side: 'domestic', adapter: api({ remove: async () => { throw new Error('移除失败，配置保留') } }) })
  try {
    await flush(); await click(button(view.root, '移除配置')); await click(button(view.root, '确认移除'))
    assert.match(text(view.root), /移除失败，配置保留/); assert.match(text(view.root), /workspace-id/)
    assert.equal(button(view.root, '确认移除').props.disabled, true)
    await click(button(view.root, '取消')); await click(button(view.root, '重新读取当前配置'))
    assert.doesNotMatch(text(view.root), /移除失败，配置保留/)
  } finally { view.close() }
})

