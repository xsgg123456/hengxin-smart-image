import { test } from 'node:test'
import assert from 'node:assert/strict'
import { IdentityError } from '../src/api/identity/request'
import { createDraftsApi, isRequirementDraft, isSourceResult, type DraftsApi, type RequirementDraft, type Requirement } from '../src/api/overseas/requirement-drafts'
import { emptyTaskDraft, validateDraft, validateNewDraft, cleanDraft } from '../src/api/overseas/tasks'
import { readyMaterialIds, type Material } from '../src/api/overseas/materials'
import { resubmitMaterialIds } from '../src/views/overseas/requirements'
import { createDraftStorage, draftStorageKey, type DraftSnapshot } from '../src/views/overseas/requirement-draft-storage'
import { createDraftController } from '../src/views/overseas/requirement-draft-controller'
import { mapRequirement } from '../src/views/overseas/requirement-source'
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v))
const fresh = (): RequirementDraft => ({ id: 'draft-1', version: 1, fields: emptyTaskDraft(), source: null, materials: [], imports: [], updatedAt: '2026-11-03', submitKey: 'stable-key', matchedDesigner: null })
const file = (id: string, kind: Material['kind'] = 'requirement'): Material => ({ id, kind, name: `${id}.pptx`, sizeBytes: 30, status: 'ready', contentType: 'application/octet-stream', taskId: null, createdAt: '2026-11-03' })
function memory() { const values = new Map<string,string>(); return { values, getItem: (key: string) => values.get(key) || null, setItem: (key: string, value: string) => { values.set(key, value) }, removeItem: (key: string) => { values.delete(key) } } }
function fakeApi(initial = fresh()) {
  let server = clone(initial)
  const api: DraftsApi = {
    get: async () => clone(server), save: async (version, fields) => { if (version !== server.version) throw new IdentityError(409, '冲突'); server = { ...server, version: version + 1, fields: clone(fields) }; return clone(server) },
    source: async () => clone(server), retry: async () => clone(server), cancel: async () => clone(server), removeMaterial: async () => clone(server), clear: async version => { if (version !== server.version) throw new IdentityError(409, '冲突'); server = { ...fresh(), id: 'new-generation', version: version + 1 }; return clone(server) }, query: async sku => ({ sku, count: 0, truncated: false, list: [] })
  }
  return { api, get: () => clone(server), set: (value: RequirementDraft) => { server = clone(value) } }
}
function setup(initial = fresh()) { const remote = fakeApi(initial), local = memory(), storage = createDraftStorage(local, 'key'), c = createDraftController(remote.api, storage); return { remote, local, storage, c } }
const full = () => ({ ...emptyTaskDraft(), name: '灯具图需', productName: '灯', brand: 'OUTON', platform: 'Amazon', language: 'en', designerId: 'designer-30', skus: [{ code: 'SKU' }] })
const requirement = (): Requirement => ({ id: 'req', platformName: '亚马逊/Amazon', brandName: 'OUTON', title: '灯具图需', productName: '灯', language: '英语', designerName: '真实设计', status: '', createdAt: '', files: [], matchedDesigner: { id: 'designer-30', name: '真实设计', department: '设计' } })
test('草稿契约使用PUT/版本/CSRF、路径编码和真实源分页信息', async () => {
  const calls: {url: string; options?: RequestInit}[] = [], api = createDraftsApi(async (url, options) => { calls.push({ url: String(url), options }); return new Response(JSON.stringify(String(url).includes('requirement-source') ? { sku: 'A/B', count: 1, truncated: false, list: [requirement()] } : fresh())) })
  await api.get(); await api.save(1, emptyTaskDraft()); await api.source(2, 'A/B', 'req', full()); await api.retry('i/1'); await api.cancel('i/1'); await api.removeMaterial('m/1'); await api.clear(4); await api.query('A/B')
  assert.equal(calls[1].options?.method, 'PUT'); assert.equal((calls[1].options?.headers as Record<string,string>)['X-HX-Request'], '1')
  assert.deepEqual(JSON.parse(String(calls[1].options?.body)), { version: 1, fields: emptyTaskDraft() }); assert.match(calls[3].url, /i%2F1\/retry$/)
  assert.equal(calls[4].options?.method, 'DELETE'); assert.match(calls[7].url, /sku=A%2FB/)
  assert.ok(isRequirementDraft(fresh())); assert.equal(isRequirementDraft({ ...fresh(), fields: { ...full(), skus: [] } }), false)
  assert.ok(isSourceResult({ sku: 'A', count: 1, truncated: false, list: [requirement()] })); assert.equal(isSourceResult({ sku: 'A', count: 1, truncated: false, list: [{ ...requirement(), matchedDesigner: { name: '伪名单' } }] }), false)
})
test('单SKU新建与历史多SKU重提验证分离；同类附件不截断且100上限', () => {
  const historical = { ...full(), skus: [{code:'A'},{code:'B'}] }
  assert.doesNotThrow(() => validateDraft(historical)); assert.throws(() => validateNewDraft(historical), /一个 SKU/)
  const files = Array.from({length:100}, (_, i) => file(String(i)))
  assert.equal(readyMaterialIds(files).length, 100); assert.equal(resubmitMaterialIds(files.map(f => ({ ...f, taskId:'t' })), 't').length,100)
  assert.throws(() => readyMaterialIds([...files,file('extra')]), /100/); assert.throws(() => readyMaterialIds([file('a'), file('a')]), /重复/)
  assert.deepEqual(cleanDraft({ ...full(), draftId:'d', draftVersion:3 }).draftVersion,3)
})
test('真实设计师映射及缺失异常字段保留已有输入', () => {
  const mapped = mapRequirement(emptyTaskDraft(), requirement()); assert.equal(mapped.fields.designerId,'designer-30'); assert.equal(mapped.fields.language,'en'); assert.equal(mapped.warnings.length,0)
  const missing = mapRequirement(full(), { ...requirement(), platformName:'异常平台', brandName:'', title:'', productName:'', language:'', matchedDesigner:null })
  assert.deepEqual(missing.fields,full()); assert.equal(missing.warnings.length,6)
})
test('初始化未完成禁止编辑，输入先落本地，再保存服务器', async () => {
  const {c,storage,remote} = setup(); c.edit(full()); assert.equal(c.state.fields.name,'')
  await c.initialize(); c.edit(full()); assert.equal(storage.read()?.fields.name,'灯具图需'); assert.equal(remote.get().fields.name,'')
  await c.flush(); assert.equal(remote.get().fields.name,'灯具图需'); assert.equal(c.state.dirty,false); assert.equal(storage.read()?.version,2); c.dispose()
})
test('请求串行且保存期间最后一次输入不会被旧响应覆盖', async () => {
  const {c,remote} = setup(); await c.initialize()
  const original = remote.api.save; let release: (() => void) | undefined, calls = 0
  remote.api.save = async (version, fields) => { calls++; if(calls===1) await new Promise<void>(r => {release=r}); return original(version,fields) }
  c.edit({ ...full(), name:'第一次' }); const pending = c.flush(); await new Promise(r=>setTimeout(r,0))
  c.edit({ ...full(), name:'最后输入' }); release!(); await pending
  assert.equal(calls,2); assert.equal(c.state.fields.name,'最后输入'); assert.equal(remote.get().fields.name,'最后输入'); c.dispose()
})
test('刷新恢复未提交不完整字段、附件、来源和中断上传提示', async () => {
  const initial = { ...fresh(), source:{sku:'SKU',requirementId:'r'}, materials:[file('a'),file('b')], imports:[{id:'i',sourceFileId:'f',filename:'附件.pdf',size:20,kind:'competitor' as const,state:'running' as const,progress:30,error:null,materialId:null}] }
  const {c,storage,remote} = setup(initial); await c.initialize(); c.edit({...emptyTaskDraft(),name:'未完成'}); c.uploads(['未完成上传.pptx']); c.dispose()
  const restored = createDraftController(remote.api,storage); await restored.initialize(); assert.equal(restored.state.fields.name,'未完成'); assert.equal(restored.state.server?.materials.length,2); assert.equal(restored.state.server?.imports[0].progress,30); assert.deepEqual(restored.state.pendingUploads,['未完成上传.pptx']); restored.dispose()
})
test('多标签版本冲突不静默覆盖；明确使用服务器或恢复本地', async () => {
  const {c,remote,storage} = setup(); await c.initialize(); c.edit({...full(),name:'本地输入'}); remote.set({...fresh(),version:2,fields:{...full(),name:'其他标签'}})
  await assert.rejects(c.flush()); assert.equal(c.state.conflict,true); assert.equal(storage.read()?.fields.name,'本地输入'); assert.equal(remote.get().fields.name,'其他标签')
  await c.resolve(true); assert.equal(remote.get().fields.name,'本地输入'); assert.equal(c.state.conflict,false); c.dispose()
  const old: DraftSnapshot = {id:'old',version:1,fields:full(),source:null,pendingUploads:[]}; storage.write(old)
  const next = createDraftController(remote.api,storage); await next.initialize(); assert.equal(next.state.conflict,true); await next.resolve(false); assert.equal(next.state.fields.name,'本地输入'); next.dispose()
})
test('来源变更冲突不能把本地旧来源字段套到新附件', async () => {
  const {c,storage,remote} = setup({...fresh(),source:{sku:'NEW',requirementId:'new'}})
  storage.write({id:'old',version:1,fields:full(),source:{sku:'OLD',requirementId:'old'},pendingUploads:[]})
  await c.initialize(); await assert.rejects(c.resolve(true), /来源已变化/); assert.equal(c.state.conflict,true); assert.equal(remote.get().source?.sku,'NEW'); c.dispose()
})
test('查询前保存正在输入字段，再更新附件进度', async () => {
  const {c,remote} = setup(); await c.initialize(); c.edit({...full(),name:'正在输入'})
  remote.set({...fresh(),materials:[file('1'),file('2')]}); await c.refresh()
  assert.equal(c.state.fields.name,'正在输入'); assert.equal(c.state.server?.materials.length,2); assert.equal(c.state.dirty,false); assert.equal(remote.get().fields.name,'正在输入'); c.dispose()
})
test('本地存储失败仍保存服务器，账号及标签存储键隔离', async () => {
  const remote = fakeApi(), c=createDraftController(remote.api,{read(){throw Error('blocked')},write(){throw Error('quota')},clear(){}})
  await c.initialize(); c.edit(full()); assert.match(c.state.localError,/无法保存/); await c.flush(); assert.equal(remote.get().fields.name,'灯具图需'); c.dispose()
  assert.notEqual(draftStorageKey('actor1','tab'),draftStorageKey('actor2','tab')); assert.notEqual(draftStorageKey('actor1','tab1'),draftStorageKey('actor1','tab2'))
})
test('清空失败保留草稿和本地，成功才更新代次', async () => {
  const {c,storage,remote} = setup(); await c.initialize(); c.edit(full()); await c.flush()
  const prior = storage.read(); await assert.rejects(c.mutate(async()=>{throw new Error('offline')},true)); assert.deepEqual(storage.read(),prior)
  await c.mutate(s=>remote.api.clear(s.version),true); assert.equal(c.state.server?.id,'new-generation'); assert.equal(c.state.fields.name,''); c.dispose()
})
test('未知提交保存原始幂等键和请求，刷新已提交任务可恢复跳转', async () => {
  const {c,storage,remote} = setup(); await c.initialize(); c.edit(full()); await c.flush()
  const body={...full(),draftId:'draft-1',draftVersion:2,materialIds:['m']}; c.submission(body,'stable-key'); c.dispose()
  const retry=createDraftController(remote.api,storage); await retry.initialize(); assert.deepEqual(retry.state.submission,{body,key:'stable-key'}); retry.dispose()
  remote.set({...fresh(),id:'consumed',version:3,lastSubmittedTaskId:'task-created',lastSubmittedKey:'stable-key'})
  const recovered=createDraftController(remote.api,storage); await recovered.initialize(); assert.equal(recovered.state.recoveredTaskId,'task-created'); recovered.completed(); assert.equal(storage.read(),undefined); recovered.dispose(); assert.equal(storage.read(),undefined)
})

test('来源变化即使字段相同也进入冲突，旧收据不能认领新提交', async () => {
  const {c,remote,storage}=setup(); await c.initialize(); c.edit(full()); await c.flush()
  remote.set({...remote.get(),source:{sku:'SKU',requirementId:'other'},version:3}); await c.refresh(); assert.equal(c.state.conflict,true); assert.equal(c.state.server?.source,null); c.dispose()
  const server={...fresh(),fields:full(),lastSubmittedTaskId:'old-task',lastSubmittedKey:'old-key'};remote.set(server)
  storage.write({id:server.id,version:server.version,fields:server.fields,source:null,pendingUploads:[],submission:{body:{...full(),materialIds:['m'],draftId:server.id,draftVersion:1},key:'new-key'}})
  const next=createDraftController(remote.api,storage);await next.initialize();assert.equal(next.state.recoveredTaskId,'');assert.equal(next.state.submission?.key,'new-key');next.dispose()
})
