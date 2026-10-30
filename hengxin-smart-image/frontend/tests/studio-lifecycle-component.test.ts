import test from 'node:test'
import assert from 'node:assert/strict'
import * as Vue from 'vue'
import { compile, all, text, simple, flush, type Node } from './membership-test-harness'
import { IdentityError } from '../src/api/identity/request'
import { archiveError } from '../src/api/overseas/archives'
import type { Studio } from '../src/api/overseas/studio'
import { handleStudioSendKey } from '../src/views/overseas/studio/studio-send-key'
import { useImagePrefetch } from '../src/views/overseas/studio/use-image-prefetch'

const node = (tag: string, value = ''): Node & { querySelector: () => null } => ({ tag, text: value, props: {}, children: [], parent: null, querySelector: () => null })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: tag => node(tag), createText: value => node('#text', value), createComment: () => node('#comment'),
  insert(child, parent, anchor) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1); child.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; parent.children.splice(i < 0 ? parent.children.length : i, 0, child) },
  remove(child) { child.parent?.children.splice(child.parent.children.indexOf(child), 1); child.parent = null },
  setText(child, value) { child.text = value }, setElementText(child, value) { child.children = []; child.text = value },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp(child, key, _old, value) { child.props[key] = value }
})
Object.defineProperty(globalThis, 'ResizeObserver', { configurable: true, value: class { observe() {} disconnect() {} } })
Object.defineProperty(globalThis, 'window', { configurable: true, value: { addEventListener() {}, removeEventListener() {} } })
const route = Vue.reactive({ query: {} as Record<string, string> })
const router = { push: async (target: { query: Record<string, string> } | string) => { if (typeof target !== 'string') route.query = target.query }, replace: async (target: { query: Record<string, string> }) => { route.query = target.query } }
const initial = (): Studio => ({ taskId: 'task', taskVersion: 4, completed: true, archiveId: 'exact-archive', reopened: false, conversationId: 'same', turns: [], materials: [], skills: [], activeTurnId: null })
const data = Vue.ref(initial()), draft = Vue.ref('保留的修改草稿'), busy = Vue.ref(false), permitted = Vue.ref(true), pending = Vue.ref<unknown>()
const locked = Vue.computed(() => data.value.completed || busy.value || !permitted.value || !!pending.value || !!data.value.activeTurnId)
const canReopen = Vue.computed(() => data.value.completed && permitted.value && !busy.value && !pending.value && !data.value.activeTurnId)
const canComplete = Vue.computed(() => !locked.value && !!data.value.archiveId)
let loseReopen = false, reopenCalls = 0, completeCalls = 0, archiveErrorStatus = 0, resolveArchive: (() => void) | undefined
const archiveCalls: string[] = []
const archiveApi = { get: async (id: string) => {
  archiveCalls.push(id)
  if (archiveErrorStatus) throw new IdentityError(archiveErrorStatus, archiveErrorStatus === 403 ? '暂无权限' : '服务暂不可用')
  if (resolveArchive) await new Promise<void>(resolve => { resolveArchive = resolve })
  return { id, taskId: 'task', sourceDeleted: false, productName: '同名商品', brand: '品牌', platform: 'Amazon', skus: [], pictureCount: 0, pictures: [], createdAt: '' }
} }
const detail = compile('views/overseas/OverseasArchiveDetail.vue', {
  '@/api/identity/request': { IdentityError }, '@/api/overseas/archives': { archiveError },
  './OverseasArchiveFields.vue': { default: simple('ArchiveFields') }, './OverseasArchivePicture.vue': { default: simple('ArchivePicture') }, './OverseasArchiveViewer.vue': { default: simple('ArchiveViewer') }
})
const unused = () => undefined
const component = compile('views/overseas/studio/OverseasStudio.vue', {
  './use-image-prefetch': { useImagePrefetch },
  'vue-router': { useRoute: () => route, useRouter: () => router },
  '@/api/overseas/archives': { createArchivesApi: () => archiveApi }, '@/api/identity/request': { IdentityError }, '../OverseasArchiveDetail.vue': { default: detail },
  './studio.css': {}, './studio-sessions.css': {}, './studio-send-key': { handleStudioSendKey },
  'element-plus': { ElMessage: { info: unused, success: unused }, ElMessageBox: { confirm: async () => undefined } },
  '@/views/hengxin/components/annotation/annotation-drafts': { forgetAnnotationDraft: unused },
  ...Object.fromEntries(['StudioTextEditor', 'StudioRecoveryDialog', 'StudioSessionList', 'StudioTurns', 'StudioArchiveFields', 'StudioAttachments', 'StudioRevisionDraft', 'StudioAnnotationDialog', 'StudioMaterials', 'StudioSkillSelect'].map(name => [`./${name}.vue`, { default: simple(name) }])),
  './use-studio-sessions': { useStudioSessions: () => ({
    sessions: Vue.ref([{ id: 'same', name: '原会话' }]), activeId: Vue.ref('same'), currentSession: Vue.ref({ id: 'same', name: '原会话' }), runningCount: Vue.ref(0), canManage: Vue.computed(() => !locked.value), sessionBusy: Vue.ref(false), sessionError: Vue.ref(''), sessionPending: Vue.ref(), preferenceNotice: Vue.ref(''), selectSession: unused, renameConversation: unused, deleteConversation: unused, saveScroll: unused, scrollPosition: Vue.ref(null), retrySession: unused,
    data, text: draft, skill: Vue.ref(''), attachments: Vue.ref([]), references: Vue.ref([]), revisions: Vue.ref([]), selected: Vue.ref([]), transcript: Vue.ref([]), error: Vue.ref(''), revisionError: Vue.ref(''), limitError: Vue.ref(''), materialNotice: Vue.ref(''),
    busy, uploading: Vue.ref(false), loading: Vue.ref(false), pending, editable: Vue.computed(() => !data.value.completed), activeTurn: Vue.ref(), locked, canSend: Vue.computed(() => !locked.value), canNewConversation: Vue.computed(() => !locked.value), canComplete, canReopen,
    refresh: unused, retry: unused, send: unused, newConversation: unused, archive: unused, stop: unused, add: unused, receive: unused, toggle: unused, toggleGroup: unused, fail: unused,
    draftKey: unused, confirmRevision: unused, removeRevision: unused, removeMaterial: unused,
    complete: async () => { completeCalls++; data.value = { ...data.value, completed: true, taskVersion: data.value.taskVersion + 1 }; return true },
    reopen: async () => { reopenCalls++; if (loseReopen) { pending.value = { key: 'same', body: { version: 4 } }; return false }; data.value = { ...data.value, completed: false, reopened: true, taskVersion: data.value.taskVersion + 1 }; return true }
  }) }
})
function open() {
  const root = node('root'), failures: unknown[] = [], app = renderer.createApp(component, { actorId: 'designer', task: { id: 'task', capabilities: ['task.design'], skus: [] }, onFailure: (e: unknown) => failures.push(e) })
  for (const name of ['ElAlert', 'ElButton', 'ElCard', 'ElDialog', 'ElInput', 'ElOption', 'ElSelect', 'ElTag']) app.component(name, simple(name))
  app.mount(root); return { root, failures, close: () => app.unmount() }
}
function button(root: Node, label: string) { const found = all(root).find(n => n.tag === 'ElButton' && text(n) === label); assert.ok(found, label); return found }
function click(root: Node, label: string) { const found = button(root, label); assert.notEqual(found.props.disabled, true); (found.props.onClick as () => void)() }
function reset() { loseReopen = false; data.value = initial(); draft.value = '保留的修改草稿'; route.query = {}; busy.value = false; permitted.value = true; pending.value = undefined; archiveErrorStatus = 0; resolveArchive = undefined; archiveCalls.length = 0; reopenCalls = 0; completeCalls = 0 }

test('正式工作台完成四步全部完成；确认解冻回③继续设计、④已有归档并可再次完成', async () => {
  reset(); const view = open()
  try {
    const steps = all(view.root).find(n => n.props['aria-label'] === '工作流进度')!
    assert.equal(all(steps).filter(n => n.tag === 'span' && n.props.class === 'finished').length, 4)
    assert.match(text(steps), /全部完成/); assert.equal(button(view.root, '发送').props.disabled, true)
    click(view.root, '解冻工作台'); await flush(); assert.equal(reopenCalls, 0, '必须二次确认')
    click(view.root, '确认解冻'); await flush()
    assert.equal(reopenCalls, 1); assert.match(text(steps), /继续设计/); assert.match(text(steps), /已有归档/)
    assert.equal(button(view.root, '发送').props.disabled, false); assert.equal(draft.value, '保留的修改草稿')
    click(view.root, '完成任务'); await flush(); assert.equal(completeCalls, 0)
    click(view.root, '确认完成'); await flush(); assert.equal(completeCalls, 1); assert.match(text(steps), /全部完成/)
  } finally { view.close() }
})

test('归档按钮将真实ID放入当前任务query，按ID加载正式详情、返回原任务保留草稿', async () => {
  reset(); const view = open()
  try {
    click(view.root, '查看本任务成品'); await flush()
    assert.equal(route.query.archive, 'exact-archive'); assert.deepEqual(archiveCalls, ['exact-archive'])
    click(view.root, '查看原任务'); await flush()
    assert.equal(route.query.archive, undefined); assert.equal(draft.value, '保留的修改草稿')
    route.query = { archive: 'exact-archive' }; await flush(); assert.deepEqual(archiveCalls, ['exact-archive', 'exact-archive'], '带query刷新/前进也打开精确详情')
  } finally { view.close() }
})

test('无归档真实说明，解冻仍可；忙、待核实、活动和无权限时解冻禁用', async () => {
  reset(); data.value.archiveId = null; const view = open()
  try {
    assert.match(text(view.root), /暂无可用归档成品/); assert.equal(button(view.root, '查看本任务成品').props.disabled, true)
    assert.equal(button(view.root, '解冻工作台').props.disabled, false)
    for (const change of [() => { busy.value = true }, () => { pending.value = {} }, () => { data.value.activeTurnId = 'running' }, () => { permitted.value = false }]) {
      busy.value = false; pending.value = undefined; data.value.activeTurnId = null; permitted.value = true; change(); await flush()
      assert.equal(button(view.root, '解冻工作台').props.disabled, true)
    }
    permitted.value = true; await flush(); click(view.root, '确认解冻'); await flush(); assert.equal(button(view.root, '完成任务').props.disabled, true)
  } finally { view.close() }
})

test('精确归档入口显示加载、删除中、不存在和无权限，错误不显示旧详情', async () => {
  for (const status of [404, 409, 403]) {
    reset(); archiveErrorStatus = status; route.query = { archive: 'exact-archive' }; const view = open()
    try {
      assert.match(text(view.root), /正在加载归档成品/)
      await flush(); const messages = all(view.root).filter(n => n.tag === 'ElAlert').map(n => n.props.title).join('')
      assert.match(messages, status === 404 ? /不存在/ : status === 409 ? /删除/ : /权限/)
      assert.equal(all(view.root).some(n => n.tag === 'ArchiveFields'), false)
      assert.equal(view.failures.length, status === 403 ? 1 : 0)
    } finally { view.close() }
  }
})


test('解冻未知结果关闭确认层露出相同请求重试入口，状态仍保持完成', async () => {
  reset(); loseReopen = true; const view = open()
  try {
    click(view.root, '解冻工作台'); await flush(); click(view.root, '确认解冻'); await flush()
    const dialog = all(view.root).find(n => n.tag === 'ElDialog' && n.props.title === '解冻工作台')!
    assert.equal(dialog.props.modelValue, false); assert.equal(data.value.completed, true)
    assert.ok(button(view.root, '核实并重试上次操作')); assert.equal(button(view.root, '解冻工作台').props.disabled, true)
  } finally { view.close() }
})

