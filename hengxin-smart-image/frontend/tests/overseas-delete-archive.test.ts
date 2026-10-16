import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createTasksApi, emptyTaskDraft, isTask, isTaskDeletion, type TaskSummary } from '../src/api/overseas/tasks'
import { archivePictureUrl, createArchivesApi, isArchiveDetail, type ArchiveDetail } from '../src/api/overseas/archives'
import { IdentityError } from '../src/api/identity/request'
const task: TaskSummary = { ...emptyTaskDraft(), id: 't/a', version: 3, name: '完整任务名称', status: 'deleting', deletionStatus: 'deleting', deletionError: null, createdAt: '', updatedAt: '', createdBy: {id:'a',name:'管理员'}, designer: {id:'d',name:'设计',status:'active',eligible:true},capabilities:['task.read','task.delete'] }
export const archive: ArchiveDetail = { id:'a/1', taskId:null, sourceDeleted:true, productName:'商品',brand:'品牌',platform:'Amazon',skus:[{code:'SKU-A'}],pictureCount:1,createdAt:'2026-10-13',pictures:[{id:'p1',name:'主图.png',sku:'SKU-A',width:16,height:16,contentType:'image/png',sizeBytes:3,url:archivePictureUrl('a/1','p1')}] }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status})
test('删除状态契约、确认正文、路径编码与权限失败不隐瞒', async () => {
  for (const status of ['deleting','delete_failed','deleted'] as const) {
    assert.ok(isTask({...task,status})); assert.ok(isTaskDeletion({taskId:task.id,status,error:null}))
  }
  assert.equal(isTask({...task,deletionError:{path:'/private'}}),false)
  assert.equal(isTaskDeletion({taskId:task.id,status:'deleted',error:3}),false)
  const calls: {url:string;options?:RequestInit}[] = []
  const api = createTasksApi(async(url,options)=>{calls.push({url:String(url),options});return json({taskId:task.id,status:'deleting',error:null})})
  const value = await api.remove(task.id,3); assert.equal(value.status,'deleting')
  await api.deletion(task.id)
  assert.equal(calls[0].url,'/api/overseas/v1/tasks/t%2Fa'); assert.equal(calls[0].options?.method,'DELETE')
  assert.equal(calls[0].options?.credentials,'include'); assert.equal((calls[0].options?.headers as Record<string,string>)['X-HX-Request'],'1')
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)),{version:3})
  assert.equal(calls[1].url,'/api/overseas/v1/tasks/t%2Fa/deletion')
  for(const status of [401,403,409,500]) await assert.rejects(createTasksApi(async()=>json({},status)).remove(task.id,3),(error:unknown)=>error instanceof IdentityError && error.status===status)
  await assert.rejects(createTasksApi(async()=>json({taskId:'other',status:'deleted',error:null})).deletion(task.id),/格式错误/)
})
test('任务不存在时归档仍独立读取与下载；拒绝外部/跨成品图片地址及错误元数据', async () => {
  assert.ok(isArchiveDetail(archive,archive.id))
  for(const value of [{...archive,pictureCount:2},{...archive,sourceDeleted:false},{...archive,pictures:[{...archive.pictures[0],url:'https://outside/image.png'}]},{...archive,pictures:[{...archive.pictures[0],url:archivePictureUrl('other','p1')}]},{...archive,pictures:[{...archive.pictures[0],sizeBytes:0}]}]) assert.equal(isArchiveDetail(value,archive.id),false)
  const calls:{url:string;options?:RequestInit}[]=[]
  const api=createArchivesApi(async(url,options)=>{calls.push({url:String(url),options});return String(url).endsWith('/download')||String(url).endsWith('/content') ? new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':'image/png'}}) : json(archive)})
  assert.deepEqual(await api.get(archive.id),archive)
  assert.equal((await api.content(archive.id,'p1')).size,3); assert.equal((await api.download(archive.id)).size,3)
  assert.deepEqual(calls.map(call=>call.url),['/api/overseas/v1/archives/a%2F1',archivePictureUrl(archive.id,'p1'),'/api/overseas/v1/archives/a%2F1/download'])
  for(const call of calls){assert.equal(call.options?.credentials,'include');assert.equal(call.options?.cache,'no-store')}
  for(const status of [401,403,404,500]) await assert.rejects(createArchivesApi(async()=>json({},status)).content(archive.id,'p1'),(error:unknown)=>error instanceof IdentityError&&error.status===status)
})

test('封面元数据只允许本套鉴权地址，详情封面必须对应归档首图', () => {
  const cover = archive.pictures[0]
  assert.ok(isArchiveDetail({ ...archive, cover }, archive.id))
  for (const value of [{ ...cover, url: 'https://external/image.png' }, { ...cover, url: archivePictureUrl('other', cover.id) }, { ...cover, sizeBytes: 0 }, { ...cover, id: 'other', url: archivePictureUrl(archive.id, 'other') }]) {
    assert.equal(isArchiveDetail({ ...archive, cover: value }, archive.id), false)
  }
})
