import test from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { getPreviewUser } from '../src/api/hengxin/session'
import type { HengxinService } from '../src/types/hengxin'
import { createMockTasks } from '../src/api/hengxin/mock-tasks'
import { createFixtures } from '../src/api/hengxin/fixtures'
async function ready(service:HengxinService,id:string){for(let i=0;i<100;i++){const detail=await service.getTask(id);if(detail.task.state==='待查看')return detail;await new Promise(r=>setTimeout(r,3))}throw Error('未完成')}
test('四角色可操作他人业务资源，返工统计及删除审计归实际操作者',async()=>{
 for(const role of ['super_admin','design_manager','designer','operator']){
  const user=getPreviewUser(`?role=${role}`);if(role==='operator')user.id='mock-operator-collaborator'
  const service=createMockService({user,delayMs:0,stepMs:1})
  try{
   const template=await service.getTemplate('t1');const before=await service.getUsage({})
   await service.saveTemplate({id:template.id,name:template.name+'协作',mode:template.mode,images:template.images,skillVersionId:template.skillVersionId,active:true,notes:'协作编辑',expectedVersion:template.version})
   await service.revise({taskId:'HX0908-001',target:1,note:'协作单图返工'});const detail=await ready(service,'HX0908-001')
   assert.equal(detail.rounds[0].operatorId,user.id);assert.equal(detail.slots[1].versions.length,2);assert.equal(detail.slots[0].versions.length,1)
   const after=await service.getUsage({});assert.equal(after.summary.single,before.summary.single+1);assert.equal(after.summary.tasks,before.summary.tasks);assert.equal(after.summary.inputTokens,null)
   const archive=await service.archive('HX0908-001');assert.equal(archive.ownerId,user.id)
   await service.deleteTemplate('t1');const receipt=await service.deleteTask('HX0908-001');assert.equal(receipt.operatorId,user.id)
   const deletedStats=await service.getUsage({});assert.deepEqual(deletedStats.summary,after.summary)
   assert.equal((await service.getArchive(archive.id)).images.length,8)
   if(['designer','operator'].includes(role)){await assert.rejects(()=>service.listUsers({page:1,pageSize:12}),/超级管理员/);await assert.rejects(()=>service.getUsage({userId:'another'}),/个人统计/)}
  }finally{service.dispose()}
 }
})
test('配置上传上限影响后续上传，监控使用本轮实际操作者',async()=>{
 const user=getPreviewUser('?role=super_admin'),service=createMockService({user,delayMs:0,stepMs:30})
 try{
  const settings=await service.getSettings();await service.saveSettings({...settings,maxUploadBytes:1048576})
  await assert.rejects(()=>service.uploadFile(new File([new Uint8Array(2*1048576)],'large.png',{type:'image/png'})),/1 MiB/)
  await service.revise({taskId:'HX0908-001',target:1,note:'管理员代操作'})
  await new Promise(r=>setTimeout(r,40));const monitor=await service.getMonitor();assert.equal(monitor.tasks.find(t=>t.taskId==='HX0908-001')?.operatorName,user.id)
 }finally{service.dispose()}
})
test('配置按返工轮次冻结，新并发设置用于后续执行',async()=>{
 const service=createMockService({user:getPreviewUser('?role=super_admin'),delayMs:0,stepMs:50})
 try{
  await service.revise({taskId:'HX0908-001',target:null,note:'旧配置任务'})
  const first=await service.getTask('HX0908-001');assert.equal(first.rounds[0].executionConfig?.version,1)
  const settings=await service.getSettings();await service.saveSettings({...settings,concurrency:2,timeoutSeconds:120})
  await service.revise({taskId:'HX0908-002',target:null,note:'新配置任务'})
  await new Promise(r=>setTimeout(r,75))
  assert.equal((await service.getMonitor()).runningCount,2)
  const old=await service.getTask('HX0908-001'),next=await service.getTask('HX0908-002')
  assert.equal(old.rounds[0].executionConfig?.timeoutSeconds,600);assert.equal(next.rounds[0].executionConfig?.timeoutSeconds,120)
 }finally{service.dispose()}
})
test('合法60秒超时配置到期停止轮次，保留旧图并计入超时统计',async()=>{
 const db=createFixtures(),engine=createMockTasks(db,async()=>{},'default',5,()=> 'mock-super-admin',()=>({version:2,concurrency:1,timeoutSeconds:60})),originalNow=Date.now
 try{
  await engine.service.revise({taskId:'HX0908-001',target:1,note:'超时保留'})
  for(let i=0;i<100 && db.tasks[0].state!=='执行中';i++)await new Promise(r=>setTimeout(r,2))
  const started=engine.getUsageAttempts().find(a=>a.operatorId==='mock-super-admin')!
  assert.ok(started);Date.now=()=>Date.parse(started.startedAt)+61000
  for(let i=0;i<100 && db.tasks[0].state!=='失败';i++)await new Promise(r=>setTimeout(r,2))
  const detail=await engine.service.getTask('HX0908-001');assert.equal(detail.task.state,'失败');assert.ok(detail.task.error?.includes('超时'));assert.equal(detail.slots[1].versions.length,1)
  assert.equal(engine.getUsageAttempts().find(a=>a.id===started.id)?.state,'timeout')
 }finally{Date.now=originalNow;engine.dispose()}
})
