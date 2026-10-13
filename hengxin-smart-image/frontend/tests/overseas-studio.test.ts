import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, defineComponent } from 'vue'
import { createStudioApi, isStudio, validateStudioFile, type Studio, type StudioApi } from '../src/api/overseas/studio'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import { IdentityError } from '../src/api/identity/request'
import { useStudio } from '../src/views/overseas/studio/use-studio'
const snapshot = (): Studio => ({ taskId:'t',completed:false,turns:[],materials:[{id:'task:m',name:'需求.pdf',contentType:'application/pdf',sizeBytes:10,url:'/api/overseas/v1/materials/m/content',source:'task'}],skills:[],activeTurnId:null })
const task: TaskDetail = {...emptyTaskDraft(),id:'t',workflow:'studio',status:'studio',version:1,createdAt:'',updatedAt:'',createdBy:{id:'u',name:'用户'},designer:{id:'d',name:'设计',status:'active',eligible:true},capabilities:['task.design'],events:[]}
const flush = async () => { for(let i=0;i<10;i++) await Promise.resolve() }
const renderer=createRenderer<object,object>({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},parentNode:()=>null,nextSibling:()=>null,patchProp(){},setText(){},setElementText(){}})
const storage = new Map<string,string>()
Object.defineProperty(globalThis,'sessionStorage',{value:{getItem:(key:string)=>storage.get(key)||null,setItem:(key:string,value:string)=>storage.set(key,value),removeItem:(key:string)=>storage.delete(key)},configurable:true})
function mount(api: StudioApi, current = () => task) {
  let state!: ReturnType<typeof useStudio>
  const failures:unknown[]=[]
  const app=renderer.createApp(defineComponent({setup(){state=useStudio(current,e=>failures.push(e),()=>{},api);return()=>null}}));app.mount({})
  return {state,failures,close:()=>app.unmount()}
}
function fake(overrides:Partial<StudioApi>={}):StudioApi {
  return {get:async()=>snapshot(),events:async()=>({items:[],cursor:0}),send:async()=>snapshot(),cancel:async()=>snapshot(),archive:async()=>snapshot(),complete:async()=>({...snapshot(),completed:true}),upload:async()=>snapshot().materials[0],content:async()=>new Blob(),...overrides}
}
test('工作台DTO拒绝跨任务与外部文件URL，上传格式边界',()=>{
  assert.equal(isStudio(snapshot(),'t'),true)
  assert.equal(isStudio(snapshot(),'other'),false)
  const bad=snapshot();bad.materials[0].url='https://example.com/private';assert.equal(isStudio(bad,'t'),false)
  for(const name of ['a.jpg','a.png','a.webp','a.pdf','a.docx','a.pptx','a.xls','a.xlsx','a.csv','a.txt'])assert.doesNotThrow(()=>validateStudioFile({name,size:1}))
  assert.throws(()=>validateStudioFile({name:'a.doc',size:1}),/转换/)
  assert.throws(()=>validateStudioFile({name:'a.ppt',size:1}),/转换/)
  assert.throws(()=>validateStudioFile({name:'a.png',size:20*1024*1024+1}),/20 MiB/)
  assert.throws(()=>validateStudioFile({name:'a.html',size:1}),/不支持/)
})
test('真实排队轮次reply为空可恢复；轮询恢复只清除读取错误',async()=>{
  const queued=snapshot();queued.turns=[{id:'r',text:'需求',skillName:null,status:'queued',reply:null,error:null,jobId:'j',jobVersion:1,attachments:[],pictures:[],referencePictures:[],createdAt:'2026-10-13'}];queued.activeTurnId='r'
  assert.equal(isStudio(queued,'t'),true)
  let failed=true
  const view=mount(fake({get:async()=>{if(failed)throw new IdentityError(0,'读取失败');return queued}}));await flush();assert.equal(view.state.error.value,'读取失败')
  failed=false;await view.state.refresh();assert.equal(view.state.error.value,'');assert.equal(view.state.data.value?.activeTurnId,'r')
  view.state.fail(Error('附件格式错误'));await view.state.refresh();assert.equal(view.state.error.value,'附件格式错误');view.close()
})
test('历史修改引用保持原轮次图片身份，拒绝跨任务地址和缺失引用字段',()=>{
  const value=snapshot(), picture={id:'p',name:'原图',url:'/api/overseas/v1/tasks/t/studio/pictures/p/content',width:800,height:800,turnId:'previous',sku:null,archived:false}
  value.turns=[{id:'new',text:'修改这张',skillName:null,status:'succeeded',reply:'已修改',error:null,jobId:'j',jobVersion:2,attachments:[],pictures:[],referencePictures:[picture],createdAt:'2026-10-13'}]
  assert.equal(isStudio(value,'t'),true)
  assert.equal(isStudio({...value,turns:[{...value.turns[0],referencePictures:undefined}]},'t'),false)
  value.turns[0].referencePictures[0].url='/api/overseas/v1/tasks/other/studio/pictures/p/content';assert.equal(isStudio(value,'t'),false)
})
test('真实API封装携带身份和幂等key、事件游标、停止版本',async()=>{
  const calls:{url:string;options?:RequestInit}[]=[]
  const api=createStudioApi(async(url,options)=>{calls.push({url:String(url),options});return new Response(JSON.stringify(String(url).includes('/events')?{items:[],cursor:9}:snapshot()))})
  await api.send('t',{text:'修改',skillId:null,attachmentIds:[],referencePictureIds:[]},'same-key')
  await api.events('t',9)
  await api.cancel('t',{id:'turn',jobVersion:3} as never)
  assert.equal(calls[0].options?.credentials,'include')
  assert.equal((calls[0].options?.headers as Record<string,string>)['Idempotency-Key'],'same-key')
  assert.match(calls[1].url,/events\?after=9/)
  assert.deepEqual(JSON.parse(String(calls[2].options?.body)),{version:3})
})
test('未知结果跨卸载恢复相同key与正文，禁止编辑后新发；确认成功才清附件',async()=>{
  storage.clear();let failed=true;const calls:{body:unknown;key:string}[]=[]
  const api=fake({send:async(_id,body,key)=>{calls.push({body,key});if(failed)throw new IdentityError(0,'连接失败');return snapshot()}})
  const first=mount(api);await flush();first.state.text.value='修改灯光';first.state.add(['task:m']);await first.state.send()
  assert.equal(first.state.attachments.value.length,1);assert.ok(first.state.pending.value);assert.equal(first.state.canSend.value,false);first.close()
  const second=mount(api);await flush();assert.ok(second.state.pending.value);failed=false;await second.state.retry()
  assert.deepEqual(calls[0],calls[1]);assert.equal(second.state.pending.value,undefined);assert.equal(storage.size,0);second.close()
})
test('素材引用不重复，移除不改源，按组选择保留其他组，归档不结束对话',async()=>{
  storage.clear();const view=mount(fake());await flush();const s=view.state
  s.add(['task:m','task:m','task:other']);assert.equal(s.attachments.value.length,1);s.attachments.value=[];assert.equal(s.data.value?.materials.length,1)
  s.toggle('outside');s.toggleGroup([{id:'a'},{id:'b'}] as never);assert.deepEqual(s.selected.value,['outside','a','b']);s.toggleGroup([{id:'a'},{id:'b'}] as never);assert.deepEqual(s.selected.value,['outside'])
  await s.archive('SKU-A');assert.equal(s.data.value?.completed,false);s.text.value='继续';assert.equal(s.canSend.value,true);view.close()
})
test('只读身份不能发送、停止或上传；失败身份读拒绝清数据',async()=>{
  storage.clear();let writes=0
  const view=mount(fake({send:async()=>{writes++;return snapshot()},upload:async()=>{writes++;return snapshot().materials[0]}}),()=>({...task,capabilities:[]}));await flush()
  view.state.text.value='不能发';await view.state.send();await view.state.receive([new File(['a'],'a.txt')]);assert.equal(writes,0);view.close()
  const denied=mount(fake({get:async()=>{throw new IdentityError(403,'失去权限')}}));await flush();assert.equal(denied.failures.length,1);assert.equal(denied.state.data.value,undefined);denied.close()
})
test('轮询响应晚于发送响应时不能回退历史；刷新保留草稿',async()=>{
  storage.clear();let late:((s:Studio)=>void)|undefined,calls=0
  const view=mount(fake({get:async()=>{if(++calls===1)return snapshot();return new Promise(resolve=>{late=resolve})},send:async()=>({...snapshot(),activeTurnId:'new-turn'})}));await flush()
  view.state.text.value='草稿';const reading=view.state.refresh();await flush();assert.equal(view.state.text.value,'草稿')
  await view.state.send();late?.(snapshot());await reading;assert.equal(view.state.data.value?.activeTurnId,'new-turn');view.close()
})
