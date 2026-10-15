import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createManagementApi, isUsage, isJobs, isSkill, isSettings, managementCapability, type Settings } from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/auth'
const settings: Settings = {version:1,paused:false,concurrency:5,timeoutSeconds:60,defaults:{analysis:null,generation:null,revision:null},autoCleanup:false}
const skill = {id:'a/b',name:'layout',displayName:'排版分析',description:'按资料分析完整商品套图'}
const usage = {jobs:1,queued:0,running:0,uncertain:1,succeeded:0,failed:0,cancelled:0,generationImages:0,revisionImages:0}
const json = (v:unknown,status=200) => new Response(JSON.stringify(v),{status})
test('管理数据拒绝缺失字段、非法范围和格式', () => {
  assert.equal(isUsage(usage),true)
  for (const v of [{...usage,jobs:-1},{...usage,uncertain:undefined}]) assert.equal(isUsage(v),false)
  assert.equal(isSkill(skill),true)
  for (const v of [{...skill,displayName:undefined},{...skill,description:null},{...skill,id:''}]) assert.equal(isSkill(v),false)
  assert.equal(isSettings(settings),true)
  for (const v of [{...settings,concurrency:6},{...settings,timeoutSeconds:9},{...settings,autoCleanup:true},{...settings,defaults:{analysis:null}}]) assert.equal(isSettings(v),false)
  assert.equal(isJobs({items:[],total:0,page:1,pageSize:20}),true)
  assert.equal(isJobs({items:[],total:-1,page:1,pageSize:20}),false)
})
test('配置写入只发送白名单字段，不传清理或环境配置', async () => {
  const api=createManagementApi(async(url,options)=>{
    assert.equal(url,'/api/overseas/v1/management/settings'); assert.equal(options?.method,'PATCH')
    assert.equal(options?.credentials,'include'); assert.equal((options?.headers as Record<string,string>)['X-HX-Request'],'1')
    assert.deepEqual(Object.keys(JSON.parse(String(options?.body))).sort(),['concurrency','defaults','paused','timeoutSeconds','version'])
    return json(settings)
  })
  await api.saveSettings(settings)
})
test('Skill 目录只读、真实中文描述，不再暴露网页写方法', async () => {
  let calls = 0
  const api = createManagementApi(async (url, options) => {
    calls++; assert.equal(url, '/api/overseas/v1/management/skills'); assert.equal(options?.method, 'GET')
    return json({items:[skill]})
  })
  assert.deepEqual((await api.skills()).items,[skill]); assert.equal(calls,1)
  for (const name of ['createSkill','publish','toggle','uploadPackage']) assert.equal(name in api,false)
})
test('统计监控编码时间、任务和分页；页面按能力放行',async()=>{
  const api=createManagementApi(async(url)=>{
    const parsed=new URL(String(url),'http://test'); assert.equal(parsed.searchParams.get('taskId'),'a/b'); assert.equal(parsed.searchParams.get('page'),'2'); assert.equal(parsed.searchParams.get('memberId'),'operator-2')
    assert.equal(parsed.searchParams.get('from'),'2026-10-12T00:00:00Z'); return json(usage)
  })
  await api.usage({memberId:'operator-2',from:'2026-10-12T00:00:00Z',to:'',taskId:'a/b',kind:'analysis',status:'uncertain',page:2,pageSize:20})
  assert.equal(managementCapability('usage'),'stats.read'); assert.equal(managementCapability('monitor'),'stats.read')
  assert.equal(managementCapability('skills'),'skills.manage'); assert.equal(managementCapability('settings'),'settings.manage')
})

test('目录错误和权限拒绝如实返回，不造空成功', async () => {
  for(const status of [401,403,500]) await assert.rejects(createManagementApi(async()=>json({},status)).skills(),(error:unknown)=>error instanceof IdentityError && error.status===status)
  await assert.rejects(createManagementApi(async()=>json({items:[{name:'missing'}]})).skills(),/格式错误/)
})

test('执行人员选项使用统计权限专用接口，作业接受历史未记录操作者', async () => {
  const api = createManagementApi(async url => { assert.equal(url, '/api/overseas/v1/management/operators'); return json({items:[{id:'other',name:'其他执行人'}]}) })
  assert.deepEqual(await api.operators(), {items:[{id:'other',name:'其他执行人'}]})
  const job = {id:'j',taskId:'t',taskName:'任务',kind:'analysis',status:'succeeded',createdAt:'',startedAt:null,completedAt:null,error:null,executionCount:1,imageCount:0,operatorId:null,operatorName:null}
  assert.equal(isJobs({items:[job],total:1,page:1,pageSize:20}),true)
  assert.equal(isJobs({items:[{...job,operatorId:'other',operatorName:'其他执行人'}],total:1,page:1,pageSize:20}),true)
  assert.equal(isJobs({items:[{...job,operatorName:undefined}],total:1,page:1,pageSize:20}),false)
})
