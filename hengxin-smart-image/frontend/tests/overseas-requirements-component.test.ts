import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as Tasks from '../src/api/overseas/tasks'
import * as Requirements from '../src/views/overseas/requirements'
import * as Types from '../src/views/overseas/types'
import * as Platforms from '../src/views/overseas/platforms'
import * as Languages from '../src/views/overseas/languages'
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
    if (path === './platforms') return Platforms
    if (path === './languages') return Languages
    if (path === './requirements') return Requirements
    if (path.endsWith('.vue')) return { default: stub(path), __esModule: true }
    throw Error(path)
  }
  new Function('require','module','exports', code)(require, module, module.exports)
  const app = renderer.createApp(module.exports.default, props)
  for (const n of ['ElCard','ElTag','ElAlert','ElForm','ElFormItem','ElInput','ElSelect','ElOption','ElButton','ElSteps','ElStep']) app.component(n, stub(n))
  const root = node(); app.mount(root)
  return { app, root, find: (tag: string) => flatten(root).find(n => n.tag === tag)!, click: async (label: string) => { const button = flatten(root).find(n => n.tag === 'ElButton' && textOf(n) === label); assert.ok(button, label); assert.ok(!button.props.disabled); (button.props.onClick as () => void)(); await flush() } }
}
const task = (status: Tasks.TaskDetail['status'] = 'pending_review'): Tasks.TaskDetail => ({ ...Tasks.emptyTaskDraft(), remarks: '', name: '任务', productName: '壳', brand: 'HX', platform: 'Amazon', language: 'de', market: '美国', skus: [{code:'A'}], id:'t', version:3,status,createdAt:'2026-10-13',updatedAt:'2026-10-13',createdBy:{id:'o',name:'运营'},designer:{id:'d',name:'设计',status:'active',eligible:true},capabilities:['task.requirements.review','task.requirements.resubmit'],events:[], requirementsReviews:[], remarks:'历史补充说明不得展示或覆盖' })
const parsed = {version:1,status:'ready',parserVersion:'test',text:'资料',error:null,createdAt:'2026-10-13'}
const material = {...parsed,id:'m',kind:'requirement',name:'图需.pdf',sizeBytes:12,contentType:'application/pdf',taskId:'t',versions:[parsed]}
test('实际审核SFC：退回必填、确认取消、409/网络失败保留意见和幂等、通过成功', async () => {
  let confirmations=0, refresh=0, changed=0, mode='network'; const keys:string[]=[]
  const api={async reviewRequirements(_id:string,_decision:string,_comment:string,_version:number,key:string) { keys.push(key); if(mode==='network')throw Error('网络失败'); if(mode==='conflict')throw new IdentityError(409,'冲突'); return {...task(),status:'analyzing'} }}
  const view=mount('OverseasRequirementsReview',{task:task(),files:[],api,materialsApi:{},onRefresh:()=>refresh++,onChanged:()=>changed++},async()=>{confirmations++;if(mode==='cancel')throw 'cancel'})
  assert.ok(!textOf(view.root).includes('历史补充说明不得展示或覆盖')); assert.ok(!textOf(view.root).includes('补充说明'));
  await view.click('退回提交人修改'); assert.equal(confirmations,0); assert.ok(flatten(view.root).some(n=>n.props.title==='请填写退回原因，便于提交人修改。'))
  const input=view.find('ElInput'); (input.props['onUpdate:modelValue'] as (v:string)=>void)('补充尺寸'); await flush()
  mode='cancel'; await view.click('退回提交人修改'); assert.equal(keys.length,0)
  mode='network'; await view.click('退回提交人修改'); assert.equal(view.find('ElInput').props.modelValue,'补充尺寸')
  await view.click('退回提交人修改'); assert.equal(keys[0],keys[1])
  mode='conflict'; await view.click('退回提交人修改'); assert.equal(refresh,1); assert.equal(view.find('ElInput').props.modelValue,'补充尺寸')
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
  const form=view.find('./OverseasCreate.vue'); const draft=form.props.modelValue as Tasks.TaskDraft; assert.equal(draft.language,'de');assert.equal(draft.platform,'Amazon');assert.equal(draft.designerId,'d');assert.equal(draft.skus[0].code,'A');draft.name='修改后的任务';draft.skus.push({code:'B'})
  assert.equal(flatten(view.root).some(n=>n.tag==='./DesignerPicker.vue'),false)
  await view.click('重新提交设计审核');assert.equal(bodies[0].name,'修改后的任务');assert.deepEqual(bodies[0].materialIds,['m']);assert.equal(bodies[0].skus.length,2)
  assert.equal(bodies[0].market, '美国'); assert.equal(bodies[0].language, 'de')
  assert.equal(Object.hasOwn(bodies[0], 'remarks'), false)
  await view.click('重新提交设计审核');assert.equal(keys[0],keys[1]);assert.equal((view.find('./OverseasCreate.vue').props.modelValue as Tasks.TaskDraft).name,'修改后的任务')
  mode='conflict';await view.click('重新提交设计审核');assert.equal(refresh,1);assert.equal((view.find('./OverseasCreate.vue').props.modelValue as Tasks.TaskDraft).skus.length,2)
  mode='ok';await view.click('重新提交设计审核');assert.equal(changed,1);view.app.unmount()
})
test('提交及修改共用表单移除站点，保留目标平台和历史值', () => {
  for (const editing of [false, true]) {
    const draft = { ...Tasks.emptyTaskDraft(), remarks: '', market: editing ? '美国' : '' }
    const view = mount('OverseasCreate', { modelValue: draft, allowed: true, editing })
    const labels = flatten(view.root).filter(n => n.tag === 'ElFormItem').map(n => n.props.label)
    assert.deepEqual(labels, [editing ? 'SKU 1' : '商品 SKU', '目标平台', '品牌', '任务名称', '品名', '语言'])
    assert.ok(!textOf(view.root).includes('补充说明'))
    assert.ok(!labels.some(label => String(label).includes('站点')))
    assert.equal(draft.market, editing ? '美国' : '')
    view.app.unmount()
  }
})
test('实际重提SFC：无站点任务仍可提交', async () => {
  let received: Tasks.TaskDraft | undefined
  const view = mount('OverseasRequirementsResubmit', {
    task: { ...task('returned'), market: '' }, materials: [material], materialsApi: {},
    api: { async resubmit(_id: string, draft: Tasks.TaskDraft) { received = draft; return task() } }
  })
  await view.click('重新提交设计审核')
  assert.equal(received?.market, '')
  assert.equal(received?.platform, 'Amazon')
  view.app.unmount()
})

test('共用真实SFC：平台和语言默认留空、语言必填且按四选项更新草稿', async () => {
  const draft = Tasks.emptyTaskDraft()
  const view = mount('OverseasCreate', { modelValue: draft, allowed: true })
  try {
    const fields = flatten(view.root).filter(n => n.tag === 'ElFormItem')
    const platform = fields.find(n => n.props.label === '目标平台')!
    const language = fields.find(n => n.props.label === '语言')!
    assert.ok(Object.hasOwn(platform.props, 'required')); assert.ok(Object.hasOwn(language.props, 'required'))
    const select = flatten(language).find(n => n.tag === 'ElSelect')!
    assert.equal(draft.platform, ''); assert.equal(select.props.modelValue, '')
    assert.equal(select.props.placeholder, '请选择语言')
    assert.equal(flatten(platform).find(n => n.tag === 'ElSelect')?.props.placeholder, '请选择目标平台')
    assert.deepEqual(flatten(language).filter(n => n.tag === 'ElOption').map(n => [n.props.value, n.props.label]), [['en','英语'],['de','德语'],['fr','法语'],['es','西班牙语']])
    for (const code of ['en','de','fr','es']) {
      ;(select.props['onUpdate:modelValue'] as (value: string) => void)(code); await flush()
      assert.equal(draft.language, code)
    }
  } finally { view.app.unmount() }
})

test('实际重提SFC：历史缺语言拒绝提交，补选后保留历史平台成功', async () => {
  for (const language of [null, undefined]) {
    let received: Tasks.TaskDraft | undefined
    const view = mount('OverseasRequirementsResubmit', {
      task: { ...task('returned'), platform: 'TikTok Shop', language }, materials: [material], materialsApi: {},
      api: { async resubmit(_id: string, draft: Tasks.TaskDraft) { received = draft; return task() } }
    })
    try {
      const draft = view.find('./OverseasCreate.vue').props.modelValue as Tasks.TaskDraft
      assert.equal(draft.platform, 'TikTok Shop'); assert.equal(draft.language, '')
      await view.click('重新提交设计审核'); assert.equal(received, undefined)
      assert.ok(flatten(view.root).some(n => n.props.title === '请选择语言（英语、德语、法语或西班牙语）'))
      draft.language = 'es'; await view.click('重新提交设计审核')
      assert.equal(received?.language, 'es'); assert.equal(received?.platform, 'TikTok Shop')
    } finally { view.app.unmount() }
  }
})
