import test from 'node:test'
import assert from 'node:assert/strict'
import * as Vue from 'vue'
import * as Tasks from '../src/api/overseas/tasks'
import * as Drafts from '../src/api/overseas/requirement-drafts'
import * as Materials from '../src/api/overseas/materials'
import * as Storage from '../src/views/overseas/requirement-draft-storage'
import * as Controller from '../src/views/overseas/requirement-draft-controller'
import * as Source from '../src/views/overseas/use-requirement-source'
import { IdentityError } from '../src/api/identity/request'
import { compile, mount, all, text, simple, flush, click, update, type Node } from './membership-test-harness'
import { fixture, deferred, fresh } from './draft-polling-fixture'

function open(f = fixture()) {
  const old = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const page = new EventTarget() as EventTarget & { hidden: boolean }; page.hidden = false
  Object.defineProperty(globalThis, 'document', { configurable: true, value: page })
  const created: string[] = []
  const component = compile('views/overseas/OverseasTaskCreate.vue', {
    'element-plus': { ElMessageBox: { confirm: async () => {} } }, '@/api/identity/request': { IdentityError },
    '@/api/overseas/tasks': Tasks, '@/api/overseas/requirement-drafts': Drafts, '@/api/overseas/materials': Materials,
    './requirement-draft-controller': Controller, './requirement-draft-storage': { ...Storage, browserDraftStorage: () => f.storage }, './use-requirement-source': Source,
    './OverseasCreate.vue': { default: Vue.defineComponent({ setup(_, { attrs, slots }) { return () => Vue.h('OverseasCreate', attrs, Object.values(slots).flatMap(s => s?.() || [])) } }) },
    './DesignerPicker.vue': { default: simple('DesignerPicker') }, './DraftMaterialsPanel.vue': { default: simple('DraftMaterialsPanel') }, './RequirementPicker.vue': { default: simple('RequirementPicker') }
  })
  const view = mount(component, { actorId: 'actor', api: {}, materialsApi: {}, draftsApi: f.api, allowed: true, onCreated: (id: string) => created.push(id) })
  return { ...view, f, page, created, visibility(hidden: boolean) { page.hidden = hidden; page.dispatchEvent(new Event('visibilitychange')) }, close() { view.close(); if (old) Object.defineProperty(globalThis, 'document', old); else Reflect.deleteProperty(globalThis, 'document') } }
}
const buttons = (root: Node) => all(root).filter(n => n.tag === 'ElButton').map(text)
const messages = (root: Node) => all(root).filter(n => n.tag === 'ElAlert').map(n => n.props.title).join(' ')
function edit(root: Node, name: string) { const form = all(root).find(n => n.tag === 'OverseasCreate')!; update(form, { ...(form.props.modelValue as Drafts.DraftFields), name }) }

test('正式新建SFC只初读一次，隐藏继续500ms自动保存，可见刷新一次，卸载清理事件与定时器', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const view = open(); t.after(() => view.close()); await flush()
  assert.equal(view.f.data.reads, 1); assert.match(text(view.root), /草稿已保存/)
  t.mock.timers.tick(60000); await flush(); assert.equal(view.f.data.reads, 1)
  view.visibility(true); edit(view.root, '隐藏时编辑'); t.mock.timers.tick(499); await flush(); assert.equal(view.f.data.writes, 0)
  t.mock.timers.tick(1); await flush(); assert.equal(view.f.data.server.fields.name, '隐藏时编辑')
  view.visibility(false); await flush(); assert.equal(view.f.data.reads, 2)
  view.close(); view.visibility(true); view.visibility(false); t.mock.timers.tick(60000); await flush(); assert.equal(view.f.data.reads, 2)
})

test('正式新建SFC连续失败显示查询重试，保存提示独立；三次后停止且按钮成功恢复', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const view = open(fixture('running')); t.after(() => view.close()); await flush()
  view.f.data.readError = '读取网络故障'
  for (let i = 0; i < 3; i++) { t.mock.timers.tick(2000); await flush() }
  assert.match(messages(view.root), /自动更新已暂停/); assert.ok(buttons(view.root).includes('重试查询')); assert.ok(!buttons(view.root).includes('重试保存'))
  assert.match(text(view.root), /草稿已保存/); assert.equal(view.f.data.reads, 4)
  t.mock.timers.tick(60000); await flush(); assert.equal(view.f.data.reads, 4)
  view.f.data.readError = ''; view.f.data.server.imports[0].state = 'ready'; click(view.root, '重试查询'); await flush()
  assert.equal(view.f.data.reads, 5); assert.ok(!buttons(view.root).includes('重试查询'))
  t.mock.timers.tick(60000); await flush(); assert.equal(view.f.data.reads, 5)
})

test('正式新建SFC读取成功不抹掉真实保存失败，读写分别重试并保留字段', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const view = open(); t.after(() => view.close()); await flush()
  view.f.data.saveError = '保存不可用'; edit(view.root, '必须保留'); t.mock.timers.tick(500); await flush()
  assert.match(text(view.root), /草稿保存失败/); assert.ok(buttons(view.root).includes('重试保存'))
  view.f.data.saveError = ''; click(view.root, '重试保存'); await flush(); assert.equal(view.f.data.server.fields.name, '必须保留')
  view.f.data.readError = '读取不可用'; view.visibility(true); view.visibility(false); await flush()
  assert.ok(buttons(view.root).includes('重试查询')); assert.ok(!buttons(view.root).includes('重试保存')); assert.match(text(view.root), /草稿已保存/)
})

test('正式新建SFC初始查询失败手动重试后仍识别精确提交收据，不丢恢复跳转', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture(); f.storage.write({ id: 'old', version: 1, fields: fresh().fields, source: null, pendingUploads: [], submission: { body: { ...fresh().fields, materialIds: [] }, key: 'submitted-key' } })
  f.data.server.lastSubmittedKey = 'submitted-key'; f.data.server.lastSubmittedTaskId = 'created-task'; f.data.readError = '初始断网'
  const view = open(f); t.after(() => view.close()); await flush()
  assert.match(text(view.root), /草稿未恢复/); assert.ok(buttons(view.root).includes('重试查询'))
  f.data.readError = ''; click(view.root, '重试查询'); await flush(); assert.deepEqual(view.created, ['created-task']); assert.equal(f.storage.read(), undefined)
})

test('正式新建SFC卸载后迟到GET不能写本地恢复副本或派发恢复任务', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const f = fixture(), gate = deferred<ReturnType<typeof fresh>>(); f.api.get = () => gate.promise
  const view = open(f); await flush(); view.close(); gate.resolve({ ...fresh(), lastSubmittedKey: 'key', lastSubmittedTaskId: 'late' }); await flush()
  assert.equal(f.storage.read(), undefined); assert.deepEqual(view.created, [])
})
