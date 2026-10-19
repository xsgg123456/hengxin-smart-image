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
let result = { ...fixture, deleteToken: 'token' }, calls = 0
let response: Archives.ArchiveDeletion = { archiveId: 'a', status: 'deleted', error: null }, rejection: unknown = null
const api = { deletionPreview: async () => result, remove: async (_id: string, token: string) => { calls++; assert.equal(token, 'token'); if (rejection) throw rejection; return response }, deletion: async () => response }
const simple = (name: string) => Vue.defineComponent({ setup(_p, { attrs, slots }) { return () => Vue.h(name, attrs, [...(slots.default?.() || []), ...(slots.footer?.() || [])]) } })
const source = readFileSync(new URL('../src/views/overseas/OverseasArchiveDelete.vue', import.meta.url), 'utf8')
const code = ts.transpileModule(compileScript(parse(source).descriptor, { id: 'delete', inlineTemplate: true }).content, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const module = { exports: {} as { default: Vue.Component } }
new Function('require', 'module', 'exports', code)((key: string) => key === 'vue' ? Vue : { IdentityError }, module, module.exports)
const all = (n: Node): Node[] => [n, ...n.children.flatMap(all)]
const text = (n: Node): string => n.text + n.children.map(text).join('')
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
const button = (root: Node, label: string) => all(root).find(n => n.tag === 'ElButton' && text(n) === label)!
async function click(root: Node, label: string) { const b = button(root,label); assert.ok(b); if (!b.props.disabled) await (b.props.onClick as () => Promise<void>)(); await flush() }
function mount(pending = false) {
 calls = 0; rejection = null; result = { ...fixture, deleteToken: 'token' }; response = { archiveId: 'a', status: 'deleted', error: null }
 const changed: Archives.ArchiveDeletion[] = [], failures: unknown[] = []
 const props = Vue.reactive({ archive: { ...fixture, deletionStatus: pending ? 'deleting' as const : null }, canDelete: true, api, onChanged: (v: Archives.ArchiveDeletion) => changed.push(v), onFailure: (v: unknown) => failures.push(v) })
 const root = node('root'), app = renderer.createApp({ render: () => Vue.h(module.exports.default, props) })
 for (const name of ['ElDialog','ElButton','ElAlert']) app.component(name,simple(name))
 app.mount(root); return {root, props, changed, failures, close: () => app.unmount()}
}
test('确认最新信息且取消不提交；确认成功通知移除',async()=>{
 const v=mount();try {
 await click(v.root,'删除整套成品');assert.match(text(v.root),/真实品名.*图片数量：1 张/)
 await click(v.root,'取消');assert.equal(calls,0)
 await click(v.root,'删除整套成品');await click(v.root,'确认删除');assert.equal(calls,1);assert.equal(v.changed[0].status,'deleted')
 }finally{v.close()}
})
test('失败安全文案和重新确认重试',async()=>{
 const v=mount();try{
 response={archiveId:'a',status:'delete_failed',error:'/secret'}
 await click(v.root,'删除整套成品');await click(v.root,'确认删除');assert.match(text(v.root),/删除未完成/);assert.doesNotMatch(text(v.root),/secret/)
 await click(v.root,'重试删除整套成品');response={archiveId:'a',status:'deleted',error:null};await click(v.root,'确认删除');assert.equal(calls,2)
 }finally{v.close()}
})
test('权限变化关闭弹窗和禁止提交',async()=>{
 const v=mount();try{
 await click(v.root,'删除整套成品');v.props.canDelete=false;await flush()
 assert.equal(all(v.root).find(n=>n.tag==='ElDialog')?.props.modelValue,false);assert.equal(button(v.root,'确认删除').props.disabled,true);assert.equal(button(v.root,'删除整套成品'),undefined);assert.equal(calls,0)
 }finally{v.close()}
})
test('冲突重新确认、缺少token禁用、权限错误通知外层',async()=>{
 const v=mount();try{
 await click(v.root,'删除整套成品');rejection=new IdentityError(409,'secret');await click(v.root,'确认删除');assert.equal(button(v.root,'确认删除').props.disabled,true)
 assert.ok(all(v.root).some(n=>n.props.title==='成品内容已变化，请关闭后重新确认。'))
 await click(v.root,'取消');result.deleteToken='';await click(v.root,'删除整套成品');assert.equal(button(v.root,'确认删除').props.disabled,true)
 await click(v.root,'取消');result.deleteToken='token';await click(v.root,'删除整套成品');rejection=new IdentityError(403,'拒绝');await click(v.root,'确认删除');assert.equal(v.failures.length,1)
 }finally{v.close()}
})
test('刷新pending恢复轮询且完成才通知deleted',async()=>{
 const v=mount(true);try{assert.equal(button(v.root,'正在删除').props.disabled,true);await new Promise(resolve=>setTimeout(resolve,2100));await flush();assert.deepEqual(v.changed.map(x=>x.status),['deleted']);assert.equal(calls,0)}finally{v.close()}
})
test('API路径和确认body、状态错误、权限冲突不隐瞒',async()=>{
 const requests:{url:string;options?:RequestInit}[]=[]
 const api=Archives.createArchivesApi(async(url,options)=>{requests.push({url:String(url),options});return new Response(JSON.stringify({archiveId:'a/b',status:'deleting',error:null}))})
 await api.remove('a/b','token');await api.deletion('a/b');assert.equal(requests[0].url,'/api/overseas/v1/archives/a%2Fb');assert.equal(requests[0].options?.method,'DELETE');assert.deepEqual(JSON.parse(String(requests[0].options?.body)),{deleteToken:'token'});assert.equal(requests[1].url,'/api/overseas/v1/archives/a%2Fb/deletion')
 for(const status of [401,403,409,500]) await assert.rejects(Archives.createArchivesApi(async()=>new Response('{}',{status})).remove('a','token'),(e:unknown)=>e instanceof IdentityError&&e.status===status)
 await assert.rejects(Archives.createArchivesApi(async()=>new Response(JSON.stringify({archiveId:'other',status:'deleted',error:null}))).deletion('a'),/格式错误/)
})

test('删除确认使用仅元数据接口，不依赖图片详情', async () => {
 const requests: string[] = []
 const { pictures: _pictures, ...summary } = { ...fixture, deleteToken: 'token' }
 const api = Archives.createArchivesApi(async url => {
  requests.push(String(url)); return new Response(JSON.stringify(summary))
 })
 assert.equal((await api.deletionPreview('a')).deleteToken, 'token')
 assert.deepEqual(requests, ['/api/overseas/v1/archives/a/deletion-preview'])
})


test('连续确认只提交一次；权限撤销丢弃迟到详情',async()=>{
 const originalRemove = api.remove, originalGet = api.deletionPreview
 const v=mount()
 try {
  await click(v.root,'删除整套成品')
  let complete!: (value: Archives.ArchiveDeletion) => void
  api.remove = async () => { calls++; return new Promise(resolve=>{complete=resolve}) }
  const confirm = button(v.root,'确认删除').props.onClick as () => Promise<void>
  const first = confirm(); await confirm(); assert.equal(calls,1)
  complete({archiveId:'a',status:'deleted',error:null}); await first
 } finally {v.close();api.remove=originalRemove}
 const next=mount()
 try {
  let complete!: (value: typeof result) => void
  api.deletionPreview = async () => new Promise(resolve=>{complete=resolve})
  const opening=(button(next.root,'删除整套成品').props.onClick as () => Promise<void>)()
  next.props.canDelete=false;await flush();complete(result);await opening;await flush()
  assert.equal(all(next.root).find(n=>n.tag==='ElDialog')?.props.modelValue,false);assert.equal(calls,0)
 }finally{next.close();api.deletionPreview=originalGet}
})
