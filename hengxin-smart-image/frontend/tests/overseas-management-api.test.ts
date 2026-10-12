import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createManagementApi, isUsage, isJobs, isSkill, isSettings, managementCapability, type Settings } from '../src/api/overseas/management'
import { IdentityError } from '../src/api/identity/auth'
const settings: Settings = {version:1,paused:false,concurrency:5,timeoutSeconds:60,defaults:{analysis:null,generation:null,revision:null},autoCleanup:false}
const skill = {id:'a/b',name:'layout',stage:'analysis',enabled:true,version:1,currentVersion:1,versions:[{version:1,files:{'SKILL.md':'instructions'},createdAt:'2026-10-12'}]}
const usage = {jobs:1,queued:0,running:0,uncertain:1,succeeded:0,failed:0,cancelled:0,generationImages:0,revisionImages:0,inputTokens:null,outputTokens:null,cost:null}
const json = (v:unknown,status=200) => new Response(JSON.stringify(v),{status})
test('管理数据拒绝虚假金额、缺失字段、非法范围和格式', () => {
  assert.equal(isUsage(usage),true)
  for (const v of [{...usage,cost:0},{...usage,inputTokens:-1},{...usage,uncertain:undefined}]) assert.equal(isUsage(v),false)
  assert.equal(isSkill(skill),true)
  for (const v of [{...skill,stage:'wallpaper'},{...skill,versions:[{version:1,files:{},createdAt:''}]}]) assert.equal(isSkill(v),false)
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
test('Skill版本发布编码ID且携带乐观版本；失败不自动重复请求', async () => {
  let calls=0
  const api=createManagementApi(async(url,options)=>{
    calls++; assert.equal(url,'/api/overseas/v1/management/skills/a%2Fb/versions')
    assert.deepEqual(JSON.parse(String(options?.body)),{version:1,files:{'SKILL.md':'new'}})
    return json({detail:'conflict'},409)
  })
  await assert.rejects(api.publish('a/b',1,{'SKILL.md':'new'}),(e:unknown)=>e instanceof IdentityError && e.status===409)
  assert.equal(calls,1)
})
test('统计监控编码时间、任务和分页；页面按能力放行',async()=>{
  const api=createManagementApi(async(url)=>{
    const parsed=new URL(String(url),'http://test'); assert.equal(parsed.searchParams.get('taskId'),'a/b'); assert.equal(parsed.searchParams.get('page'),'2')
    assert.equal(parsed.searchParams.get('from'),'2026-10-12T00:00:00Z'); return json(usage)
  })
  await api.usage({from:'2026-10-12T00:00:00Z',to:'',taskId:'a/b',kind:'analysis',status:'uncertain',page:2,pageSize:20})
  assert.equal(managementCapability('usage'),'stats.read'); assert.equal(managementCapability('monitor'),'stats.read')
  assert.equal(managementCapability('skills'),'skills.manage'); assert.equal(managementCapability('settings'),'settings.manage')
})
