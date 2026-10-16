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
  return {removeMaterial:async()=>snapshot(),get:async()=>snapshot(),transcript:async()=>({items:[],cursor:0,hasMore:false}),newConversation:async()=>({...snapshot(),conversationId:"new"}),events:async()=>({items:[],cursor:0}),send:async()=>snapshot(),cancel:async()=>snapshot(),archive:async()=>snapshot(),complete:async()=>({...snapshot(),completed:true}),upload:async()=>snapshot().materials[0],...overrides}
}
test('工作台DTO拒绝跨任务与外部文件URL，上传格式边界',()=>{
  assert.equal(isStudio(snapshot(),'t'),true)
  assert.equal(isStudio(snapshot(),'other'),false)
  const bad=snapshot();bad.materials[0].url='https://example.com/private';assert.equal(isStudio(bad,'t'),false)
  for(const name of ['a.jpg','a.png','a.webp','a.pdf','a.docx','a.pptx','a.xls','a.xlsx','a.csv','a.txt'])assert.doesNotThrow(()=>validateStudioFile({name,size:1}))
  assert.throws(()=>validateStudioFile({name:'a.doc',size:1}),/转换/)
  assert.throws(()=>validateStudioFile({name:'a.ppt',size:1}),/转换/)
  assert.throws(()=>validateStudioFile({name:'a.png',size:500_000_000+1}),/500 MB/)
  assert.throws(()=>validateStudioFile({name:'a.html',size:1}),/不支持/)
})
test('工作台 Skill 与管理目录共用中文名称和描述契约，不要求版本或阶段',()=>{
  const value=snapshot();value.skills=[{id:'old',name:'walmart-old',displayName:'沃尔玛新品主图 · 原版',description:'原版说明'},{id:'new',name:'walmart-new',displayName:'沃尔玛新品主图 · 新版（9.27）',description:'新版说明'}]
  assert.equal(isStudio(value,'t'),true)
  assert.equal(isStudio({...value,skills:[{id:'old',name:'walmart-old',version:1}]},'t'),false)
  assert.equal(isStudio({...value,skills:[{...value.skills[0],description:null}]},'t'),false)
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

test('自动读取静默，空闲30秒，执行1秒，完成与卸载停止',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});storage.clear()
  let calls=0,current=snapshot()
  const view=mount(fake({get:async()=>{calls++;return structuredClone(current)}}));await flush()
  assert.equal(calls,1);assert.equal(view.state.loading.value,false)
  view.state.text.value='保留草稿';view.state.skill.value='skill';view.state.add(['task:m'])
  t.mock.timers.tick(29999);await flush();assert.equal(calls,1)
  current.activeTurnId='running';t.mock.timers.tick(1);await flush();assert.equal(calls,2)
  assert.equal(view.state.loading.value,false);assert.equal(view.state.text.value,'保留草稿');assert.equal(view.state.skill.value,'skill');assert.equal(view.state.attachments.value.length,1)
  t.mock.timers.tick(999);await flush();assert.equal(calls,2)
  t.mock.timers.tick(1);await flush();assert.equal(calls,3)
  current={...snapshot(),completed:true};t.mock.timers.tick(1000);await flush();assert.equal(calls,4)
  t.mock.timers.tick(60000);await flush();assert.equal(calls,4)
  await view.state.refresh();assert.equal(calls,5);view.close()
  t.mock.timers.tick(60000);await flush();assert.equal(calls,5)
})

test('隐藏页暂停自动请求，恢复可见立即同步并移除卸载监听',async t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  const page=new EventTarget() as EventTarget & {visibilityState:string};page.visibilityState='visible'
  Object.defineProperty(globalThis,'document',{value:page,configurable:true})
  let calls=0
  const view=mount(fake({get:async()=>{calls++;return snapshot()}}))
  try {
    await flush();page.visibilityState='hidden';page.dispatchEvent(new Event('visibilitychange'))
    t.mock.timers.tick(90000);await flush();assert.equal(calls,1)
    page.visibilityState='visible';page.dispatchEvent(new Event('visibilitychange'));await flush();assert.equal(calls,2)
    assert.equal(view.state.loading.value,false)
    view.close();page.dispatchEvent(new Event('visibilitychange'));t.mock.timers.tick(90000);await flush();assert.equal(calls,2)
  } finally {Reflect.deleteProperty(globalThis,'document')}
})

test('手动刷新加入后台在途请求显示loading，无重叠；网络错误恢复自动重试',async t=>{
  t.mock.timers.enable({apis:['setTimeout']})
  let resolve!: (value:Studio)=>void,calls=0,failRead=false
  const view=mount(fake({get:async()=>{calls++;if(failRead)throw Error('网络中断');if(calls===2)return new Promise(done=>{resolve=done});return snapshot()}}));await flush()
  t.mock.timers.tick(30000);await flush();assert.equal(calls,2);assert.equal(view.state.loading.value,false)
  const manual=view.state.refresh();assert.equal(view.state.loading.value,true);assert.equal(calls,2)
  t.mock.timers.tick(90000);await flush();assert.equal(calls,2)
  resolve(snapshot());await manual;assert.equal(view.state.loading.value,false)
  failRead=true;t.mock.timers.tick(30000);await flush();assert.equal(view.state.error.value,'网络中断');assert.equal(view.state.loading.value,false)
  failRead=false;t.mock.timers.tick(30000);await flush();assert.equal(view.state.error.value,'');assert.equal(calls,4);view.close()
})

test('过期读取错误和卸载后的响应不能覆盖新的操作结果或报错',async()=>{
  storage.clear();let reject!: (reason:Error)=>void,calls=0
  const view=mount(fake({get:async()=>{if(++calls===1)return snapshot();return new Promise((_resolve,fail)=>{reject=fail})},send:async()=>({...snapshot(),activeTurnId:'latest'})}));await flush()
  const pending=view.state.refresh();view.state.text.value='新轮次';await view.state.send()
  reject(new IdentityError(403,'旧请求权限失败'));await pending
  assert.equal(view.state.data.value?.activeTurnId,'latest');assert.equal(view.failures.length,0);assert.equal(view.state.error.value,'')
  const later=view.state.refresh();view.close();reject(Error('已卸载'));await later;assert.equal(view.state.error.value,'')
})

test('自动权限拒绝停止轮询，手动重试可恢复',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});let denied=true,calls=0
  const view=mount(fake({get:async()=>{calls++;if(denied)throw new IdentityError(403,'无权限');return snapshot()}}));await flush()
  t.mock.timers.tick(90000);await flush();assert.equal(calls,1)
  denied=false;await view.state.refresh();assert.equal(view.state.error.value,'');t.mock.timers.tick(30000);await flush();assert.equal(calls,3);view.close()
})

test('增量快照立即翻页、更新原位置、断线从最后确认游标恢复且保留失败文字',async()=>{
  storage.clear();let fail=false;const cursors:number[]=[]
  const entry=(id:number,itemId:string,text:string)=>({id,turnId:'r',itemId,text,kind:'message' as const,state:'completed' as const,createdAt:''})
  const view=mount(fake({transcript:async(_id,after)=>{cursors.push(after);if(fail)throw Error('离线');return after===0?{items:[entry(1,'a','第一条'),entry(2,'b','第二条')],cursor:2,hasMore:true}:after===2?{items:[entry(3,'a','第一条完整更新')],cursor:3,hasMore:false}:{items:[entry(3,'a','不应覆盖')],cursor:3,hasMore:false}}}));await flush()
  assert.deepEqual(cursors,[0,2]);assert.deepEqual(view.state.transcript.value.map(e=>e.text),['第一条完整更新','第二条'])
  fail=true;await view.state.refresh();assert.equal(view.state.error.value,'离线');assert.equal(view.state.transcript.value.length,2)
  fail=false;await view.state.refresh();assert.deepEqual(cursors,[0,2,3,3]);assert.equal(view.state.transcript.value[0].text,'第一条完整更新');assert.equal(view.state.error.value,'');view.close()
})

test('新会话未知结果保留草稿引用并以相同key重试，成功才清空且历史保留',async()=>{
  storage.clear();let failed=true;const keys:string[]=[]
  const old={...snapshot(),conversationId:'old'}
  const view=mount(fake({get:async()=>old,newConversation:async(_id,key)=>{keys.push(key);if(failed)throw new IdentityError(0,'断线');return {...old,conversationId:'new'}}}));await flush()
  const s=view.state;s.text.value='草稿';s.skill.value='skill';s.add(['task:m']);s.references.value=[{id:'p'}] as never;s.selected.value=['p']
  assert.equal(s.canNewConversation.value,true);await s.newConversation();assert.equal(s.canNewConversation.value,false);assert.equal(s.text.value,'草稿');assert.equal(s.attachments.value.length,1)
  await s.newConversation();assert.equal(keys.length,1);failed=false;await s.retry();assert.equal(keys[0],keys[1]);assert.equal(s.data.value?.conversationId,'new')
  assert.equal(s.text.value,'');assert.equal(s.skill.value,'');assert.deepEqual(s.attachments.value,[]);assert.deepEqual(s.references.value,[]);assert.deepEqual(s.selected.value,[]);assert.equal(s.data.value?.materials.length,1);view.close()
})

test('新会话在执行中/只读禁用，发送正文保留前后空白',async()=>{
  storage.clear();let writes=0,sent=''
  const view=mount(fake({get:async()=>({...snapshot(),activeTurnId:'r'}),newConversation:async()=>{writes++;return snapshot()},send:async(_id,body)=>{sent=body.text;return snapshot()}}));await flush()
  assert.equal(view.state.canNewConversation.value,false);await view.state.newConversation();assert.equal(writes,0)
  view.state.data.value!.activeTurnId=null;view.state.text.value='  原样正文\n';await view.state.send();assert.equal(sent,'  原样正文\n');view.close()
})

test('新契约API携带会话幂等key、transcript游标并拒绝恶意状态',async()=>{
  const calls:{url:string;options?:RequestInit}[]=[]
  const api=createStudioApi(async(url,options)=>{calls.push({url:String(url),options});return new Response(JSON.stringify(String(url).includes('/transcript')?{items:[],cursor:8,hasMore:false}:{...snapshot(),conversationId:'c'}))})
  await api.newConversation('t','conversation-key');await api.transcript('t',8)
  assert.equal(calls[0].url,'/api/overseas/v1/tasks/t/studio/conversations');assert.equal(calls[0].options?.body,'{}');assert.equal((calls[0].options?.headers as Record<string,string>)['Idempotency-Key'],'conversation-key')
  assert.match(calls[1].url,/transcript\?after=8/)
  const bad=createStudioApi(async()=>new Response(JSON.stringify({items:[{id:1,turnId:'r',itemId:'x',kind:'secret',text:'x',state:'completed',createdAt:''}],cursor:1,hasMore:false})))
  await assert.rejects(()=>bad.transcript('t',0),/响应格式/)
})

test('页面隐藏中止在途transcript并忽略晚到内容，返回按原游标补齐',async()=>{
  storage.clear();const page=new EventTarget() as EventTarget & {visibilityState:string};page.visibilityState='visible';Object.defineProperty(globalThis,'document',{value:page,configurable:true})
  let signal:AbortSignal|undefined,resolve!:(value:{items:never[];cursor:number;hasMore:boolean})=>void,calls=0
  const view=mount(fake({transcript:async(_id,_after,s)=>{calls++;signal=s;if(calls===1)return new Promise(done=>{resolve=done});return {items:[],cursor:0,hasMore:false}}}))
  try{await flush();page.visibilityState='hidden';page.dispatchEvent(new Event('visibilitychange'));assert.equal(signal?.aborted,true);resolve({items:[],cursor:12,hasMore:false});await flush();page.visibilityState='visible';page.dispatchEvent(new Event('visibilitychange'));await flush();assert.equal(calls,2);assert.equal(view.state.error.value,'')}finally{view.close();Reflect.deleteProperty(globalThis,'document')}
})

test('普通附件100项边界：超额批次不上传、引用去重、移除后可继续', async()=>{
  storage.clear(); let uploads=0, sent=0
  const view=mount(fake({upload:async()=>({...snapshot().materials[0],id:`upload:${++uploads}`}),send:async()=>{sent++;return snapshot()}}));await flush();const s=view.state
  s.attachments.value=Array.from({length:99},(_,i)=>({...snapshot().materials[0],id:`upload:${i}`}))
  await s.receive([new File(['x'],'a.txt'),new File(['x'],'b.txt')]);assert.equal(uploads,0);assert.match(s.error.value,/100 个附件/);assert.equal(s.attachments.value.length,99)
  s.add(['task:m','task:m']);assert.equal(s.attachments.value.length,100)
  s.add(['task:m']);assert.equal(s.attachments.value.length,100)
  await s.receive([new File(['x'],'a.txt')]);assert.equal(uploads,0)
  s.attachments.value.pop();await s.receive([new File(['x'],'a.txt')]);assert.equal(uploads,1);assert.equal(s.attachments.value.length,100)
  assert.equal(s.canSend.value,true);await s.send();assert.equal(sent,1);view.close()
})

test('生成图片100张独立上限；绕过添加的101项发送兜底保留草稿',async()=>{
  storage.clear();let sent=0
  const view=mount(fake({send:async()=>{sent++;return snapshot()}}));await flush();const s=view.state
  s.text.value='保留意见';s.attachments.value=Array.from({length:100},(_,i)=>({...snapshot().materials[0],id:`upload:${i}`}))
  const picture={id:'p',name:'图',url:'/api/overseas/v1/tasks/t/studio/pictures/p/content',width:1,height:1,turnId:'r',sku:null,archived:false}
  for(let i=0;i<100;i++)s.modify({...picture,id:`p${i}`})
  s.modify({...picture,id:'p0'});assert.equal(s.references.value.length,100)
  s.modify({...picture,id:'p100'});assert.equal(s.references.value.length,100);assert.match(s.error.value,/100 张/);assert.equal(s.canSend.value,true)
  s.attachments.value.push({...snapshot().materials[0],id:'extra'});assert.equal(s.canSend.value,false);await s.send();assert.equal(sent,0);assert.match(s.limitError.value,/100 个/);assert.equal(s.text.value,'保留意见')
  s.attachments.value.pop();s.references.value.push(picture);assert.equal(s.canSend.value,false);assert.match(s.limitError.value,/100 张/)
  s.references.value.pop();await s.send();assert.equal(sent,1);view.close()
})

test('sessionStorage中的101项超限消息恢复为可移除草稿，不困在pending锁中',async()=>{
  storage.clear();let calls=0
  const value=snapshot();value.materials=Array.from({length:101},(_,i)=>({...snapshot().materials[0],id:`upload:${i}`}))
  storage.set('hx-studio-pending::t',JSON.stringify({key:'oversized',kind:'send',body:{text:'原始草稿',skillId:'skill',attachmentIds:value.materials.map(a=>a.id),referencePictureIds:[]}}))
  const view=mount(fake({get:async()=>value,send:async()=>{calls++;return snapshot()}}));await flush();const s=view.state
  assert.equal(s.pending.value,undefined);assert.equal(storage.size,0);assert.equal(s.locked.value,false);assert.equal(s.text.value,'原始草稿');assert.equal(s.skill.value,'skill');assert.equal(s.attachments.value.length,101)
  await s.send();assert.equal(calls,0);assert.match(s.limitError.value,/100 个附件/)
  s.attachments.value.pop();await s.send();assert.equal(calls,1);view.close()
})


test('素材移除只更新右侧列表，保留历史、待发送附件与输入，随后可正常发送',async()=>{
  storage.clear();let current=snapshot();let sent:unknown
  const view=mount(fake({get:async()=>current,removeMaterial:async()=>{current={...current,materials:[]};return current},send:async(_id,body)=>{sent=body;return current}}));await flush()
  view.state.add(['task:m']);view.state.text.value='继续使用该附件';view.state.skill.value='skill'
  const original=view.state.attachments.value[0]
  assert.equal(await view.state.removeMaterial('task:m'),true)
  assert.equal(view.state.data.value?.materials.length,0);assert.deepEqual(view.state.attachments.value,[original]);assert.equal(view.state.text.value,'继续使用该附件')
  await view.state.send();assert.deepEqual(sent,{text:'继续使用该附件',skillId:'skill',attachmentIds:['task:m'],referencePictureIds:[]});view.close()
})

test('移除失败不删列表；只读和已完成任务不调用移除接口',async()=>{
  storage.clear();let calls=0
  const api=fake({removeMaterial:async()=>{calls++;throw new IdentityError(500,'移除失败')}})
  const view=mount(api);await flush();assert.equal(await view.state.removeMaterial('task:m'),false);assert.equal(view.state.data.value?.materials.length,1);assert.equal(view.state.error.value,'移除失败');view.close()
  for(const current of [()=>({...task,capabilities:[]}),()=>task]){
    const readonly=mount(fake({...api,get:async()=>({...snapshot(),completed:current().capabilities.length>0})}),current);await flush();await readonly.state.removeMaterial('task:m');readonly.close()
  }
  assert.equal(calls,1)
})

test('素材移除接口编码身份并携带浏览器写保护和身份 cookie',async()=>{
  let url='',options:RequestInit|undefined
  const api=createStudioApi(async(u,o)=>{url=String(u);options=o;return new Response(JSON.stringify(snapshot()))})
  await api.removeMaterial('t','upload:file-id')
  assert.match(url,/materials\/upload%3Afile-id$/);assert.equal(options?.method,'DELETE');assert.equal(options?.credentials,'include');assert.ok((options?.headers as Record<string,string>)['X-HX-Request'])
})

test('重复上传保留新的发送附件身份并刷新去重列表，恢复提示可见',async()=>{
  storage.clear();let reads=0
  const view=mount(fake({get:async()=>{reads++;return snapshot()},upload:async()=>({...snapshot().materials[0],id:'upload:new',materialState:'restored'})}));await flush()
  await view.state.receive([new File(['same'],'重命名.pdf')]);await flush()
  assert.equal(view.state.attachments.value[0].id,'upload:new');assert.equal(view.state.data.value?.materials.length,1);assert.ok(reads>=2);assert.match(view.state.materialNotice.value,/已恢复/);view.close()
})
