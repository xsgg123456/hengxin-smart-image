import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Tasks from '../src/api/overseas/tasks'
import * as Requirements from '../src/views/overseas/requirements'
import * as Types from '../src/views/overseas/types'
import { IdentityError } from '../src/api/identity/request'
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
const stub = (name: string) => Vue.defineComponent({ inheritAttrs: false, setup(_, { attrs, slots }) { return () => Vue.h(name, attrs, Object.values(slots).flatMap(s => s?.() || [])) } })
function mount(name: string, props: Record<string, unknown>, confirm: () => Promise<unknown> = async () => {}) {
  const source = readFileSync(new URL(`../src/views/overseas/${name}.vue`, import.meta.url), 'utf8')
  const compiled = compileScript(parse(source).descriptor, { id: 'requirements-test', inlineTemplate: true })
  const code = ts.transpileModule(compiled.content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const module = { exports: {} as { default: Vue.Component } }
  const require = (path: string): unknown => {
    if (path === 'vue') return Vue
    if (path === 'element-plus') return { ElMessageBox: { confirm } }
    if (path.endsWith('/tasks')) return Tasks
    if (path.endsWith('/request')) return { IdentityError }
    if (path === './types') return Types
    if (path === './requirements') return Requirements
    if (path.endsWith('.vue')) return { default: stub(path), __esModule: true }
    throw Error(path)
  }
  new Function('require','module','exports', code)(require, module, module.exports)
  const app = renderer.createApp(module.exports.default, props)
  for (const n of ['ElCard','ElTag','ElAlert','ElForm','ElFormItem','ElInput','ElButton','ElSteps','ElStep']) app.component(n, stub(n))
  const root = node(); app.mount(root)
  return { app, root, find: (tag: string) => flatten(root).find(n => n.tag === tag)!, click: async (label: string) => { const button = flatten(root).find(n => n.tag === 'ElButton' && textOf(n) === label); assert.ok(button, label); assert.ok(!button.props.disabled); (button.props.onClick as () => void)(); await flush() } }
}
const task = (status: Tasks.TaskDetail['status'] = 'pending_review'): Tasks.TaskDetail => ({ ...Tasks.emptyTaskDraft(), name: '任务', productName: '壳', brand: 'HX', market: '美国', skus: [{code:'A'}], id:'t', version:3,status,createdAt:'2026-10-13',updatedAt:'2026-10-13',createdBy:{id:'o',name:'运营'},designer:{id:'d',name:'设计',status:'active',eligible:true},capabilities:['task.requirements.review','task.requirements.resubmit'],events:[], requirementsReviews:[] })
const parsed = {version:1,status:'ready',parserVersion:'test',text:'资料',error:null,createdAt:'2026-10-13'}
const material = {...parsed,id:'m',kind:'requirement',name:'图需.pdf',sizeBytes:12,contentType:'application/pdf',taskId:'t',versions:[parsed]}
test('实际审核SFC：退回必填、确认取消、409/网络失败保留意见和幂等、通过成功', async () => {
  let confirmations=0, refresh=0, changed=0, mode='network'; const keys:string[]=[]
  const api={async reviewRequirements(_id:string,_decision:string,_comment:string,_version:number,key:string) { keys.push(key); if(mode==='network')throw Error('网络失败'); if(mode==='conflict')throw new IdentityError(409,'冲突'); return {...task(),status:'analyzing'} }}
  const view=mount('OverseasRequirementsReview',{task:task(),files:[],api,materialsApi:{},onRefresh:()=>refresh++,onChanged:()=>changed++},async()=>{confirmations++;if(mode==='cancel')throw 'cancel'})
  await view.click('退回运营修改'); assert.equal(confirmations,0); assert.ok(flatten(view.root).some(n=>n.props.title==='请填写退回原因，便于运营修改。'))
  const input=view.find('ElInput'); (input.props['onUpdate:modelValue'] as (v:string)=>void)('补充尺寸'); await flush()
  mode='cancel'; await view.click('退回运营修改'); assert.equal(keys.length,0)
  mode='network'; await view.click('退回运营修改'); assert.equal(view.find('ElInput').props.modelValue,'补充尺寸')
  await view.click('退回运营修改'); assert.equal(keys[0],keys[1])
  mode='conflict'; await view.click('退回运营修改'); assert.equal(refresh,1); assert.equal(view.find('ElInput').props.modelValue,'补充尺寸')
  mode='ok'; await view.click('审核通过，进入 AI 分析'); assert.equal(changed,1); assert.equal(view.find('ElInput').props.modelValue,''); view.app.unmount()
})
test('实际审核SFC：无权限隐藏操作，卸载后迟到成功不派发', async()=>{
  const denied=mount('OverseasRequirementsReview',{task:{...task(),capabilities:[]},files:[],api:{},materialsApi:{}}); assert.equal(flatten(denied.root).filter(n=>n.tag==='ElInput').length,0); denied.app.unmount()
  let resolve!:(value:Tasks.TaskDetail)=>void, changed=0
  const view=mount('OverseasRequirementsReview',{task:task(),files:[],api:{reviewRequirements:()=>new Promise(r=>{resolve=r})},materialsApi:{},onChanged:()=>changed++})
  await view.click('审核通过，进入 AI 分析'); view.app.unmount(); resolve(task()); await flush(); assert.equal(changed,0)
})
test('实际重提SFC：绑定资料保留、字段SKU回填、失败/409保留修改、成功回审核',async()=>{
  let mode='network',refresh=0,changed=0; const bodies:Tasks.TaskDraft[]=[], keys:string[]=[]
  const api={async resubmit(_id:string,draft:Tasks.TaskDraft,_version:number,key:string){bodies.push(draft);keys.push(key);if(mode==='network')throw Error('网络失败');if(mode==='conflict')throw new IdentityError(409,'冲突');return task()}}
  const view=mount('OverseasRequirementsResubmit',{task:task('returned'),materials:[material],api,materialsApi:{},onRefresh:()=>refresh++,onChanged:()=>changed++})
  const form=view.find('./OverseasCreate.vue'); const draft=form.props.modelValue as Tasks.TaskDraft; assert.equal(draft.designerId,'d');assert.equal(draft.skus[0].code,'A');draft.name='修改后的任务';draft.skus.push({code:'B'})
  assert.equal(flatten(view.root).some(n=>n.tag==='./DesignerPicker.vue'),false)
  await view.click('重新提交设计审核');assert.equal(bodies[0].name,'修改后的任务');assert.deepEqual(bodies[0].materialIds,['m']);assert.equal(bodies[0].skus.length,2)
  await view.click('重新提交设计审核');assert.equal(keys[0],keys[1]);assert.equal((view.find('./OverseasCreate.vue').props.modelValue as Tasks.TaskDraft).name,'修改后的任务')
  mode='conflict';await view.click('重新提交设计审核');assert.equal(refresh,1);assert.equal((view.find('./OverseasCreate.vue').props.modelValue as Tasks.TaskDraft).skus.length,2)
  mode='ok';await view.click('重新提交设计审核');assert.equal(changed,1);view.app.unmount()
})
