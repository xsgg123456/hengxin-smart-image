import * as BeijingTime from '../src/utils/beijing-time'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Tasks from '../src/api/overseas/tasks'
import * as Archives from '../src/api/overseas/archives'
import * as Management from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/request'
import { useArchiveImage } from '../src/views/overseas/use-archive-image'
interface Node { tag: string; children: Node[]; parent: Node | null; props: Record<string, unknown>; text: string }
const node = (text = '', tag = ''): Node => ({ tag, children: [], parent: null, props: {}, text })
const renderer = Vue.createRenderer<Node, Node>({
  createElement: tag => node('', tag), createText: node, createComment: node,
  insert(child, parent, anchor = null) { child.parent = parent; const i = anchor ? parent.children.indexOf(anchor) : -1; if (i < 0) parent.children.push(child); else parent.children.splice(i, 0, child) },
  remove(child) { const p = child.parent; if (p) p.children.splice(p.children.indexOf(child), 1); child.parent = null },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
  patchProp: (el, key, _old, value) => { el.props[key] = value }, setText: (el, text) => { el.text = text }, setElementText: (el, text) => { el.text = text }
})
const flush = async () => { for (let i = 0; i < 15; i++) { await Promise.resolve(); await Vue.nextTick() } }
const flatten = (n: Node): Node[] => [n, ...n.children.flatMap(flatten)]
const textOf = (n: Node): string => n.text + n.children.map(textOf).join('')
const downloads: {blob: Blob; name: string}[] = []
const stub = (name: string) => Vue.defineComponent({ inheritAttrs: false, setup(_, { attrs, slots }) { return () => attrs.modelValue === false && name === 'ElDialog' ? null : Vue.h(name, attrs, name === 'ArtTable' ? [] : Object.values(slots).flatMap(slot => slot?.() || [])) } })
function component(name: string): Vue.Component {
  const source = readFileSync(new URL(`../src/views/overseas/${name}.vue`, import.meta.url), 'utf8')
  const compiled = compileScript(parse(source).descriptor, { id: 'delete-test', inlineTemplate: true })
  const code = ts.transpileModule(compiled.content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  const require = (path: string): unknown => {
    if (path === 'vue') return Vue
    if (path === 'element-plus') return { ElImageViewer: stub('ElImageViewer') }
    if (path.endsWith('/use-archive-image')) return { useArchiveImage }
    if (path === '@/utils/beijing-time') return BeijingTime
    if (path.endsWith('/tasks')) return Tasks
    if (path.endsWith('/archives')) return Archives
    if (path.endsWith('/management')) return Management
    if (path.endsWith('/request')) return { IdentityError }
    if (path.endsWith('/pictures')) return { saveBlob: (blob: Blob, name: string) => downloads.push({blob,name}) }
    if (path.includes('art-table')) return { default: stub('ArtTable'), __esModule: true }
    if (path.endsWith('OverseasSkillCatalog.vue')) return { default: component('admin/OverseasSkillCatalog'), __esModule: true }
    if (path.endsWith('OverseasArchiveFields.vue')) return { default: component('OverseasArchiveFields'), __esModule: true }
    if (path.endsWith('OverseasArchivePicture.vue')) return { default: stub('OverseasArchivePicture'), __esModule: true }
    if (path.endsWith('OverseasArchiveViewer.vue')) return { default: stub('OverseasArchiveViewer'), __esModule: true }
    throw Error(path)
  }
  new Function('require', 'module', 'exports', code)(require, module, module.exports)
  return module.exports.default
}
function mount(name: string, props: Record<string, unknown>) {
  const app = renderer.createApp(component(name), props)
  for (const n of ['ElTag', 'ElCard', 'ElAlert', 'ElForm', 'ElFormItem', 'ElInput', 'ElButton', 'ElDialog', 'ElImage']) app.component(n, stub(n))
  const root = node(); app.mount(root)
  const find = (tag: string) => flatten(root).find(n => n.tag === tag)!
  const button = (label: string) => flatten(root).find(n => n.tag === 'ElButton' && textOf(n) === label)
  return { app, root, find, button, async click(label: string) { const target = button(label); assert.ok(target, label); assert.ok(!target.props.disabled, label); (target.props.onClick as () => void)(); await flush() }, async type(value: string) { (find('ElInput').props['onUpdate:modelValue'] as (value: string) => void)(value); await flush() } }
}
const task = (capabilities = ['task.read', 'task.delete']): Tasks.TaskDetail => ({ ...Tasks.emptyTaskDraft(), id: 'task', name: '完整任务名称', version: 2, status: 'studio', createdAt: '', updatedAt: '', createdBy: { id: 'a', name: '管理员' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities, events: [] })
test('真实删除 SFC：无权限隐藏，仅二次确认，进行中不伪报删除、轮询失败及版本化重试', async () => {
  const denied = mount('OverseasTaskDelete', { task: task(['task.read']), api: {} }); assert.equal(denied.button('删除'), undefined); denied.app.unmount()
  const changes: Tasks.TaskDeletion[] = [], writes: unknown[] = []
  let resolve!: (value: Tasks.TaskDeletion) => void, mode = 'pending'
  const api = { get: async () => ({ ...task(), version: mode === 'retry' ? 4 : 2 }), remove: async (_id: string, version: number) => { writes.push({ version }); return mode === 'retry' ? { taskId: 'task', status: 'deleted', error: null } : new Promise<Tasks.TaskDeletion>(r => { resolve = r }) }, deletion: async () => ({ taskId: 'task', status: 'delete_failed', error: '文件暂不可用，请重试' }) }
  const view = mount('OverseasTaskDelete', { task: task(), api, onChanged: (value: Tasks.TaskDeletion) => changes.push(value) })
  await view.click('删除'); assert.equal(view.button('确认删除')?.props.disabled, false)
  assert.equal(view.find('ElInput'), undefined); assert.ok(textOf(view.root).includes('任务：完整任务名称')); assert.equal(writes.length, 0)
  const confirm = view.button('确认删除')!.props.onClick as () => void
  await view.click('确认删除'); confirm(); await flush(); assert.equal(writes.length, 1)
  assert.equal(changes.length, 0); assert.equal(view.button('确认删除')?.props.disabled, true); assert.equal(view.find('ElDialog').props['show-close'], false)
  resolve({ taskId: 'task', status: 'deleting', error: null }); await flush()
  assert.equal(changes[0].status, 'deleting'); assert.equal(view.button('正在删除')?.props.disabled, true)
  await new Promise(resolve => setTimeout(resolve, 2100)); await flush()
  assert.equal(changes.at(-1)?.status, 'delete_failed'); assert.ok(textOf(view.root).includes('文件暂不可用'))
  mode = 'retry'; await view.click('重试删除'); assert.equal(view.find('ElInput'), undefined); await view.click('确认删除')
  assert.equal(changes.at(-1)?.status, 'deleted'); assert.deepEqual(writes, [{ version: 2 }, { version: 4 }]); view.app.unmount()
})
test('真实删除 SFC：取消不写入，409保留确认并更新版本，网络未知只读核实，卸载忽略迟到结果', async () => {
  let writes = 0, reads = 0, current = 2, mode = 'conflict', resolve!: (value: Tasks.TaskDeletion) => void
  const changes: Tasks.TaskDeletion[] = []
  const api = { get: async () => ({ ...task(), version: current }), remove: async (_id: string, version: number) => { writes++; if (mode === 'conflict') { current++; throw new IdentityError(409, '冲突') } if (mode === 'unknown') throw new IdentityError(0, '连接中断'); assert.equal(version, current); return new Promise<Tasks.TaskDeletion>(r => { resolve = r }) }, deletion: async () => { reads++; return { taskId: 'task', status: 'deleting', error: null } } }
  const view = mount('OverseasTaskDelete', { task: task(), api, onChanged: (value: Tasks.TaskDeletion) => changes.push(value) })
  await view.click('删除'); await view.click('取消'); assert.equal(writes, 0)
  await view.click('删除'); await view.click('确认删除'); assert.equal(writes, 1); assert.equal(view.find('ElInput'), undefined)
  mode = 'unknown'; await view.click('确认删除'); assert.equal(reads, 1); assert.equal(writes, 2); assert.equal(changes.at(-1)?.status, 'deleting'); view.app.unmount()
  mode = 'slow'; const late = mount('OverseasTaskDelete', { task: task(), api, onChanged: (value: Tasks.TaskDeletion) => changes.push(value) })
  await late.click('删除'); await late.click('确认删除'); late.app.unmount(); const count = changes.length; resolve({ taskId: 'task', status: 'deleted', error: null }); await flush(); assert.equal(changes.length, count)
})
test('实际 Skill SFC：状态只读、名称描述搜索、空/失败区分、刷新恢复与权限拒绝', async () => {
  let mode = 'data'; const failures: unknown[] = []
  const skills = [{id:'old',name:'walmart-old',displayName:'沃尔玛新品主图 · 原版',description:'完整描述\n参考图说明'}, {id:'new',name:'walmart-new',displayName:'沃尔玛新品主图 · 新版（9.27）',description:'新版差异'}]
  const view = mount('admin/OverseasLiveSkills', { api: { skills: async () => { if (mode === 'error') throw Error('目录不可用'); if (mode === 'denied') throw new IdentityError(403, '暂无权限'); return {items: mode === 'empty' ? [] : skills.map(skill => ({...skill,enabled:true,version:1})),canToggle:false} } }, onFailure: (reason: unknown) => failures.push(reason) })
  await flush(); const table = view.find('ArtTable'); assert.equal((table.props.data as unknown[]).length, 2)
  assert.deepEqual((table.props.columns as {label:string}[]).map(c => c.label), ['名称','描述','状态'])
  assert.equal(view.button('添加 Skill'), undefined); assert.equal(view.find('ElDialog'), undefined)
  await view.type('参考图'); assert.equal((view.find('ArtTable').props.data as unknown[]).length, 1)
  await view.type('不存在'); assert.match(String(view.find('ArtTable').props['empty-text']), /暂无匹配/)
  await view.type(''); mode = 'empty'; await view.click('刷新 Skill'); assert.equal((view.find('ArtTable').props.data as unknown[]).length, 0); assert.equal(view.find('ArtTable').props['empty-text'], '暂无已安装 Skill')
  mode = 'error'; await view.click('刷新 Skill'); assert.equal(view.find('ArtTable'), undefined); assert.equal(view.find('ElAlert').props.title, '目录不可用')
  mode = 'data'; await view.click('刷新 Skill'); assert.equal((view.find('ArtTable').props.data as unknown[]).length, 2)
  mode = 'denied'; await view.click('刷新 Skill'); assert.equal(failures.length, 1); assert.equal(view.find('ArtTable'), undefined); view.app.unmount()
})
test('实际归档详情 SFC：原任务已删时独立读取，保留图片、权限错误清详情，卸载忽略迟到数据', async () => {
  const picture={id:'p',name:'主图.png',sku:'A',width:10,height:10,contentType:'image/png',sizeBytes:3,url:'/api/overseas/v1/archives/a/pictures/p/content'}
  const archive={id:'a',taskId:null,sourceDeleted:true,productName:'产品',brand:'HX',platform:'Amazon',skus:[{code:'A'}],pictureCount:1,createdAt:'',pictures:[picture]}
  let mode='ok',reads=0,resolve!:(value:unknown)=>void;const failures:unknown[]=[]
  const api={get:async(id:string)=>{assert.equal(id,'a');reads++;if(mode==='denied')throw new IdentityError(403,'成品无权限');if(mode==='slow')return new Promise(r=>{resolve=r});return archive}}
  const view=mount('OverseasArchiveDetail',{id:'a',api,onFailure:(reason:unknown)=>failures.push(reason)});await flush()
  assert.equal(reads,1);assert.ok(textOf(view.root).includes('原任务已删除'));assert.equal(view.button('查看原任务'),undefined);assert.deepEqual(view.find('OverseasArchivePicture').props.picture,picture)
  mode='denied';await view.click('刷新成品详情');assert.equal(failures.length,1);assert.equal(view.find('OverseasArchivePicture'),undefined);view.app.unmount()
  mode='slow';const late=mount('OverseasArchiveDetail',{id:'a',api});await flush();late.app.unmount();resolve(archive);await flush();assert.equal(late.find('OverseasArchivePicture'),undefined)
})
test('实际归档图片 SFC：真实字节生成预览/下载，元数据不符拒绝、403上报、卸载中止读取', async () => {
  downloads.length=0;const picture={id:'p',name:'主图.png',sku:'A',width:10,height:10,contentType:'image/png',sizeBytes:3,url:'/api/overseas/v1/archives/a/pictures/p/content'}
  let mode='ok',signal:AbortSignal|undefined,resolve!:(value:Blob)=>void;const failures:unknown[]=[]
  const blob=new Blob([new Uint8Array([1,2,3])],{type:'image/png'})
  const api={content:async(id:string,pictureId:string,controller:AbortSignal)=>{assert.equal(id,'a');assert.equal(pictureId,'p');signal=controller;if(mode==='wrong')return new Blob(['wrong']);if(mode==='denied')throw new IdentityError(403,'图片无权限');if(mode==='slow')return new Promise<Blob>(r=>{resolve=r});return blob}}
  const view=mount('OverseasArchivePicture',{archiveId:'a',picture,api});await flush();assert.match(String(view.find('ElImage').props.src),/^blob:/);await view.click('下载图片');assert.equal(downloads[0].blob,blob);assert.equal(downloads[0].name,picture.name);view.app.unmount();assert.equal(signal?.aborted,true)
  mode='wrong';const wrong=mount('OverseasArchivePicture',{archiveId:'a',picture,api,onFailure:(reason:unknown)=>failures.push(reason)});await flush();assert.ok(textOf(wrong.root).includes('图片文件与归档记录不一致'));assert.equal(wrong.button('下载图片')?.props.disabled,true)
  mode='denied';await wrong.click('重新加载图片');assert.equal(failures.length,1);wrong.app.unmount()
  mode='slow';const late=mount('OverseasArchivePicture',{archiveId:'a',picture,api});await flush();late.app.unmount();assert.equal(signal?.aborted,true);resolve(blob);await flush();assert.equal(late.find('ElImage'),undefined)
})

const archivePictures: Archives.ArchivePicture[] = [0, 1, 2].map(index => ({ id: `p${index}`, name: `图${index}.png`, sku: 'A', width: 10, height: 10, contentType: 'image/png', sizeBytes: 3, url: Archives.archivePictureUrl('a', `p${index}`) }))
const imageBlob = () => new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' })
test('整套查看器按点击索引加载，切图释放Blob，乱序响应不能串图，关闭中止读取', async () => {
  const calls: string[] = [], pending = new Map<string, (blob: Blob) => void>(), signals: AbortSignal[] = [], revoked: string[] = []
  const original = URL.revokeObjectURL
  URL.revokeObjectURL = value => { revoked.push(value); original(value) }
  try {
    const api = { content: async (id: string, picture: string, signal: AbortSignal) => { assert.equal(id, 'a'); calls.push(picture); signals.push(signal); return new Promise<Blob>(resolve => pending.set(picture, resolve)) } }
    const view = mount('OverseasArchiveViewer', { archiveId: 'a', api, group: archivePictures, initialIndex: 1 })
    await flush(); assert.deepEqual(calls, ['p1']); assert.equal(view.find('ElImageViewer').props['initial-index'], 1); assert.equal(view.find('ElImageViewer').props.infinite, false)
    pending.get('p1')!(imageBlob()); await flush()
    const first = (view.find('ElImageViewer').props['url-list'] as string[])[1]; assert.match(first, /^blob:/)
    const next = view.find('ElImageViewer').props.onSwitch as (index: number) => void
    next(2); await flush(); assert.ok(revoked.includes(first)); assert.equal(signals[0].aborted, true)
    next(0); await flush(); assert.equal(signals[1].aborted, true)
    pending.get('p2')!(imageBlob()); await flush(); assert.ok((view.find('ElImageViewer').props['url-list'] as string[]).every(url => !url.startsWith('blob:')))
    pending.get('p0')!(imageBlob()); await flush(); assert.match((view.find('ElImageViewer').props['url-list'] as string[])[0], /^blob:/)
    assert.match(textOf(view.root), /1 \/ 3/); view.app.unmount(); assert.equal(signals[2].aborted, true); assert.equal(revoked.length, 2)
  } finally { URL.revokeObjectURL = original }
})
test('查看器详情失败、图片失败及解码失败可重试，权限失效不保留Blob', async () => {
  let mode = 'metadata', failures: unknown[] = [], reads = 0
  const api = { get: async () => { if (mode === 'metadata') throw Error('暂时离线'); return { pictures: archivePictures } }, content: async () => { reads++; if (mode === 'image') throw Error('存储不可用'); if (mode === 'denied') throw new IdentityError(401, '身份已失效'); return imageBlob() } }
  const view = mount('OverseasArchiveViewer', { archiveId: 'a', api, initialIndex: 0, onFailure: (reason: unknown) => failures.push(reason) })
  await flush(); assert.match(textOf(view.root), /暂时离线/); assert.equal(reads, 0)
  mode = 'image'; await view.click('重新加载图片'); assert.match(textOf(view.root), /存储不可用/)
  mode = 'ok'; await view.click('重新加载图片'); assert.match((view.find('ElImageViewer').props['url-list'] as string[])[0], /^blob:/)
  ;(view.find('ElImageViewer').props.onError as () => void)(); await flush(); assert.match(textOf(view.root), /图片无法显示/)
  await view.click('重新加载图片'); assert.doesNotMatch(textOf(view.root), /图片无法显示/)
  mode = 'denied'; (view.find('ElImageViewer').props.onSwitch as (index: number) => void)(1); await flush()
  assert.equal(failures.length, 1); assert.ok((view.find('ElImageViewer').props['url-list'] as string[]).every(url => !url.startsWith('blob:'))); view.app.unmount()
})
test('封面仅请求首图，点击直接发出预览，旧归档缺封面时鉴权读取详情恢复', async () => {
  let metadataReads = 0, preview = 0; const reads: string[] = []
  const api = { get: async () => { metadataReads++; return { pictures: archivePictures } }, content: async (_id: string, id: string) => { reads.push(id); return imageBlob() } }
  const archive = { id: 'a', productName: '产品', pictureCount: 3, cover: archivePictures[0] }
  const view = mount('OverseasArchiveCover', { archive, api, onPreview: () => preview++ }); await flush()
  assert.deepEqual(reads, ['p0']); assert.equal(metadataReads, 0); assert.match(textOf(view.root), /共 3 张/)
  ;(view.find('button').props.onClick as () => void)(); await flush(); assert.equal(preview, 1); assert.equal(metadataReads, 0); view.app.unmount()
  const legacy = mount('OverseasArchiveCover', { archive: { ...archive, cover: null }, api }); await flush()
  assert.equal(metadataReads, 1); assert.deepEqual(reads, ['p0', 'p0']); legacy.app.unmount()
})
test('详情点击任意图片传入同套顺序和对应索引，关闭预览保留详情', async () => {
  const archive = { id: 'a', productName: '产品', sourceDeleted: true, taskId: null, brand: '品牌', platform: 'Amazon', skus: [{ code: 'A' }], pictureCount: 3, pictures: archivePictures }
  const view = mount('OverseasArchiveDetail', { id: 'a', api: { get: async () => archive } }); await flush()
  const cards = flatten(view.root).filter(n => n.tag === 'OverseasArchivePicture')
  ;(cards[2].props.onPreview as () => void)(); await flush()
  assert.equal(view.find('OverseasArchiveViewer').props['initial-index'], 2)
  assert.deepEqual(view.find('OverseasArchiveViewer').props.group, archivePictures)
  ;(view.find('OverseasArchiveViewer').props.onClose as () => void)(); await flush()
  assert.equal(view.find('OverseasArchiveViewer'), undefined); assert.ok(view.find('OverseasArchivePicture')); view.app.unmount()
})
