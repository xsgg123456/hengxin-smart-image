import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import { IdentityError, type Member } from '../src/api/identity/auth'
import { createOverseasRevalidator } from '../src/api/identity/revalidate'

interface HostNode { children: HostNode[]; parent: HostNode | null; props: Record<string, unknown>; text: string }
const node = (text = ''): HostNode => ({ children: [], parent: null, props: {}, text })
const renderer = Vue.createRenderer<HostNode, HostNode>({
  createElement: () => node(), createText: node, createComment: node,
  insert(child, parent, anchor = null) { child.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(child); else parent.children.splice(i, 0, child) },
  remove(child) { const p = child.parent; if (p) p.children.splice(p.children.indexOf(child), 1); child.parent = null },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp: (el, key, _old, value) => { el.props[key] = value }, setText: (el, text) => { el.text = text },
  setElementText: (el, text) => { el.text = text }
})
const source = readFileSync(new URL('../src/views/auth/IdentityPortal.vue', import.meta.url), 'utf8')
const compiled = compileScript(parse(source).descriptor, { id: 'portal-test', inlineTemplate: true })
const code = ts.transpileModule(compiled.content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const flush = async () => { for (let i = 0; i < 10; i++) { await Promise.resolve(); await Vue.nextTick() } }

for (const failure of [0,401,403,503]) test(`真实IdentityPortal组件重验：${failure || '同身份保留草稿'}，含挂body弹层锁定`, async () => {
  const win = Object.assign(new EventTarget(), { location: { hash: '#/overseas/admin/users' } })
  const doc = Object.assign(new EventTarget(), { visibilityState: 'visible', body: { inert: false } })
  const person: Member = { id: 'one', name: '测试成员', status: 'active', identitySessionId: 'identity-1', roles: ['super_admin'], capabilities: ['members.manage'] }
  let mounted = 0, unmounted = 0, pending = false, checks = 0
  let finish!: () => void
  const draft = Vue.ref('未保存内容')
  const child = Vue.defineComponent({ setup() { Vue.onMounted(() => { mounted++ }); Vue.onUnmounted(() => { unmounted++ }); return () => Vue.h('input', { value: draft.value }) } })
  const empty = Vue.defineComponent({ render: () => Vue.h('span') })
  const api = {
    config: async () => ({ configured: true }), me: async () => { checks++; return { name: person.name, sessionId: person.identitySessionId } },
    access: async () => ({ state: 'allowed', member: person }),
    overseasMe: async () => { if (pending) await new Promise<void>(resolve => { finish = resolve }); if (failure && pending) throw new IdentityError(failure, 'denied'); return person }
  }
  const module = { exports: {} as { default: Vue.Component } }
  const require = (name: string): unknown => {
    if (name === 'vue') return Vue
    if (name === 'element-plus') return { ElMessage: { success: () => {} }, ElMessageBox: { confirm: async () => {}, close: () => {} } }
    if (name.endsWith('/revalidate')) return { createOverseasRevalidator }
    if (name.endsWith('/auth')) return { identityApi: api, IdentityError }
    if (name.endsWith('/container-auth')) return { requestContainerAuthCode: async () => '' }
    if (name.endsWith('OverseasPortal.vue')) return { default: child, __esModule: true }
    if (name.endsWith('.vue')) return { default: empty, __esModule: true }
    if (name.startsWith('@imgs/')) return ''
    throw new Error('Unexpected test dependency: ' + name)
  }
  // Compile the actual SFC; only IO and child screens are substituted.
  new Function('require', 'module', 'exports', 'window', 'document', code)(require, module, module.exports, win, doc)
  const app = renderer.createApp(module.exports.default)
  for (const name of ['ElButton','ElAlert']) app.component(name, empty)
  app.mount(node()); await flush()
  assert.equal(mounted, 1); assert.equal(unmounted, 0)
  draft.value = '仍未保存的修改'; pending = true
  win.dispatchEvent(new Event('focus')); doc.dispatchEvent(new Event('visibilitychange')); await flush()
  assert.equal(doc.body.inert, true, 'body弹层必须一同锁定')
  assert.equal(mounted, 1); assert.equal(unmounted, 0, '不能先卸载再重建业务页')
  assert.equal(checks, 4, '初始加载及准入/页面确认+一次去重核验')
  finish(); await flush()
  assert.equal(doc.body.inert, false)
  assert.equal(win.location.hash, '#/overseas/admin/users')
  assert.equal(unmounted, failure ? 1 : 0)
  if (!failure) assert.equal(draft.value, '仍未保存的修改')
  app.unmount(); assert.equal(doc.body.inert, false)
})
