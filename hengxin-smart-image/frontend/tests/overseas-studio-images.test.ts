import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, defineComponent } from 'vue'
import { type Studio, type StudioApi } from '../src/api/overseas/studio'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import { IdentityError } from '../src/api/identity/request'
import { annotationDraft } from '../src/views/hengxin/components/annotation/annotation-drafts'
import { studioDraftKey } from '../src/views/overseas/studio/studio-revisions'
import { checkImage, imageUrl, isImage, loadStudioImage } from '../src/views/overseas/studio/studio-images'
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

const resultPicture = (id = 'picture') => ({id,name:'生成图.png',url:`/api/overseas/v1/tasks/t/studio/pictures/${id}/content`,width:800,height:800,turnId:'previous',sku:null,archived:false})
const annotationAsset = (id = 'annotation') => ({id:`upload:${id}`,name:'标注.png',url:`/api/overseas/v1/tasks/t/studio/files/${id}/content`,contentType:'image/png',sizeBytes:20,source:'upload' as const})

test('确认标注真实上传并回填，保留草稿和普通附件，不自动发送；发送保持明确文件对应',async()=>{
  storage.clear();let uploads=0;const calls:unknown[]=[]
  const view=mount(fake({upload:async()=>{uploads++;return annotationAsset()},send:async(_id,body)=>{calls.push(body);return snapshot()}}));await flush();const s=view.state
  s.text.value='  主输入原文\n';s.skill.value='selected';s.add(['task:m'])
  assert.equal(await s.confirmRevision(resultPicture(),{text:'标注 1（框选）：去除反光',file:new File(['png'],'annotation.png',{type:'image/png'})}),true)
  assert.equal(uploads,1);assert.equal(calls.length,0);assert.equal(s.text.value,'  主输入原文\n');assert.equal(s.skill.value,'selected');assert.equal(s.attachments.value.length,2);assert.equal(s.references.value.length,1)
  await s.send();assert.deepEqual(calls,[{text:'  主输入原文\n',skillId:'selected',attachmentIds:['task:m','upload:annotation'],referencePictureIds:['picture'],imageEdits:[{pictureId:'picture',annotationId:'upload:annotation',text:'标注 1（框选）：去除反光'}]}])
  assert.equal(s.revisions.value.length,0);assert.equal(s.attachments.value.length,0);view.close()
})

test('重复编辑替换旧标注，失败保留已确认摘要和草稿，取消只去除该次修改',async()=>{
  storage.clear();let uploads=0,failed=false
  const view=mount(fake({upload:async()=>{if(failed)throw new IdentityError(500,'上传失败');return annotationAsset(String(++uploads))}}));await flush();const s=view.state
  const file=new File(['png'],'annotation.png',{type:'image/png'});s.text.value='补充';s.add(['task:m'])
  await s.confirmRevision(resultPicture(),{text:'第一版',file});failed=true
  assert.equal(await s.confirmRevision(resultPicture(),{text:'失败稿',file}),false);assert.equal(s.revisions.value[0].text,'第一版');assert.deepEqual(s.attachments.value.map(a=>a.id),['task:m','upload:1']);assert.equal(s.text.value,'补充')
  failed=false;await s.confirmRevision(resultPicture(),{text:'第二版',file});assert.deepEqual(s.attachments.value.map(a=>a.id),['task:m','upload:2']);assert.equal(s.references.value.length,1);assert.equal(s.revisions.value.length,1)
  s.removeRevision('picture');assert.deepEqual(s.attachments.value.map(a=>a.id),['task:m']);assert.equal(s.references.value.length,0);assert.equal(s.text.value,'补充');view.close()
})

test('无标注仅回填原图，所有修改都须有意见，空意见必须由主输入补充',async()=>{
  storage.clear();let uploads=0
  const view=mount(fake({upload:async()=>{uploads++;return annotationAsset()}}));await flush();const s=view.state
  await s.confirmRevision(resultPicture(),{text:''});assert.equal(uploads,0);assert.equal(s.canSend.value,false);assert.match(s.revisionError.value,/补充/)
  await s.confirmRevision(resultPicture('second'),{text:'第二张的修改'});assert.equal(s.canSend.value,false)
  s.text.value='第一张调整对比度';assert.equal(s.canSend.value,true)
  const file=new File(['png'],'a.png');assert.equal(await s.confirmRevision(resultPicture(),{text:' ',file}),false);assert.equal(uploads,0)
  view.close()
})

test('标注与原图计入各自100限制，满额重编辑替换允许，超额不上传且保留草稿',async()=>{
  storage.clear();let uploads=0
  const view=mount(fake({upload:async()=>annotationAsset(String(++uploads))}));await flush();const s=view.state
  s.attachments.value=Array.from({length:99},(_,i)=>annotationAsset(`existing-${i}`));s.references.value=Array.from({length:99},(_,i)=>resultPicture(`existing-${i}`))
  const file=new File(['png'],'a.png');await s.confirmRevision(resultPicture(),{text:'初版',file});assert.equal(s.attachments.value.length,100);assert.equal(s.references.value.length,100)
  await s.confirmRevision(resultPicture(),{text:'替换版',file});assert.equal(uploads,2);assert.equal(s.attachments.value.length,100)
  assert.equal(await s.confirmRevision(resultPicture('extra'),{text:'超额',file}),false);assert.equal(uploads,2);assert.equal(s.revisions.value[0].text,'替换版')
  s.attachments.value.pop();assert.equal(await s.confirmRevision(resultPicture('extra'),{text:'超额原图'}),false);assert.match(s.error.value,/100 张/)
  view.close()
})

test('标注发送未知结果跨卸载原样重试，不重新上传，不更换key或文件ID',async()=>{
  storage.clear();let uploads=0,failed=true;const calls:{body:unknown;key:string}[]=[]
  const api=fake({upload:async()=>{uploads++;return annotationAsset()},send:async(_id,body,key)=>{calls.push({body,key});if(failed)throw new IdentityError(0,'连接失败');return snapshot()}})
  const first=mount(api);await flush();await first.state.confirmRevision(resultPicture(),{text:'标注 1（画笔）：变亮',file:new File(['png'],'a.png')});await first.state.send()
  assert.equal(first.state.locked.value,true);first.close()
  const second=mount(api);await flush();assert.ok(second.state.pending.value);failed=false;await second.state.retry();assert.deepEqual(calls[0],calls[1]);assert.equal(uploads,1);assert.equal(storage.size,0);second.close()
})

test('标注草稿键隔离身份/任务/会话/图片，取消、成功发送和新会话清理',async()=>{
  assert.equal(new Set([studioDraftKey('u','t','c','p'),studioDraftKey('u2','t','c','p'),studioDraftKey('u','t2','c','p'),studioDraftKey('u','t','c2','p'),studioDraftKey('u','t','c','p2')]).size,5)
  storage.clear();const view=mount(fake());await flush();const s=view.state,p=resultPicture(),key=s.draftKey(p)
  await s.confirmRevision(p,{text:'修改'});annotationDraft(key).general='待清理';s.removeRevision(p.id);assert.equal(annotationDraft(key).general,'')
  await s.confirmRevision(p,{text:'修改'});annotationDraft(key).general='待清理';await s.send();assert.equal(annotationDraft(key).general,'')
  await s.confirmRevision(p,{text:'修改'});annotationDraft(key).general='待清理';await s.newConversation();assert.equal(annotationDraft(key).general,'');assert.equal(s.revisions.value.length,0);view.close()
})

test('仅JPEG/PNG/WebP附件使用inline地址，原图保持路由；鉴权失效可识别',async()=>{
  const asset=annotationAsset(),picture=resultPicture(),signal=new AbortController().signal
  assert.equal(isImage(asset),true);assert.equal(isImage({...asset,contentType:'image/svg+xml'}),false);assert.equal(isImage(snapshot().materials[0]),false);assert.equal(isImage(picture),true)
  assert.equal(imageUrl(asset),asset.url+'?preview=true');assert.equal(imageUrl(picture),picture.url)
  const calls:{url:string;options?:RequestInit}[]=[]
  await checkImage(asset,signal,async(url,options)=>{calls.push({url:String(url),options});return new Response(null,{status:200})})
  assert.equal(calls[0].options?.method,'HEAD');assert.equal(calls[0].options?.credentials,'include');assert.match(calls[0].url,/preview=true$/)
  await assert.rejects(()=>checkImage(asset,signal,async()=>new Response(null,{status:401})),e=>e instanceof IdentityError && e.status===401)
  await assert.rejects(()=>loadStudioImage(picture,signal,async()=>new Response(null,{status:403})),e=>e instanceof IdentityError && e.status===403)
})

test('只读身份不上传标注；401上传失败触发身份处理且不添加摘要',async()=>{
  storage.clear();let uploads=0;const api=fake({upload:async()=>{uploads++;throw new IdentityError(401,'身份已失效')}})
  const readonly=mount(api,()=>({...task,capabilities:[]}));await flush();assert.equal(await readonly.state.confirmRevision(resultPicture(),{text:'改亮',file:new File(['png'],'a.png')}),false);assert.equal(uploads,0);readonly.close()
  const view=mount(api);await flush();assert.equal(await view.state.confirmRevision(resultPicture(),{text:'改亮',file:new File(['png'],'a.png')}),false);assert.equal(view.failures.length,1);assert.equal(view.state.data.value,undefined);assert.equal(view.state.revisions.value.length,0);view.close()
})


test('上传标注期间对话变化或卸载，不把迟到附件回填到新上下文',async()=>{
  storage.clear();let resolve!:(asset:ReturnType<typeof annotationAsset>)=>void
  const view=mount(fake({get:async()=>({...snapshot(),conversationId:'old'}),upload:()=>new Promise(done=>{resolve=done})}));await flush();const s=view.state
  const operation=s.confirmRevision(resultPicture(),{text:'修改',file:new File(['png'],'a.png')});s.data.value!.conversationId='new';resolve(annotationAsset());assert.equal(await operation,false);assert.equal(s.revisions.value.length,0);assert.equal(s.attachments.value.length,0);assert.match(s.error.value,/对话已变化/)
  const late=s.confirmRevision(resultPicture(),{text:'修改',file:new File(['png'],'a.png')});view.close();resolve(annotationAsset());assert.equal(await late,false);assert.equal(s.revisions.value.length,0)
})
