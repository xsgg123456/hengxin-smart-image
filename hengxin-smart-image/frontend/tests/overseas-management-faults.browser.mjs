import { mkdir } from 'node:fs/promises'
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({headless:true})
const context = await browser.newContext({viewport:{width:1280,height:900}})
const page = await context.newPage(), errors = [], queries = []
page.setDefaultTimeout(15000); page.on('pageerror',e=>errors.push(e.message))
let role = 'super_admin', mode = '', writes = 0
const allCaps = ['stats.read','members.manage','skills.manage','settings.manage']
let caps = [...allCaps]
let settings = {version:1,paused:false,concurrency:5,timeoutSeconds:60,defaults:{analysis:null,generation:null,revision:null},autoCleanup:false}
let skills = []
const summary = {jobs:1,queued:0,running:0,uncertain:0,succeeded:1,failed:0,cancelled:0,generationImages:1,revisionImages:0,inputTokens:null,outputTokens:null,cost:null}
const job = {id:'j1',taskId:'t1',taskName:'真实范围作业',kind:'analysis',status:'succeeded',executionCount:1,imageCount:1,inputTokens:null,outputTokens:null,createdAt:'2026-10-12',startedAt:null,completedAt:null,error:null}
const go = async path => { await page.goto(base + '/#/overseas/admin/' + path) }
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.deepEqual(await locator.evaluate(el=>{
    const b=el.getBoundingClientRect(),fail=[]
    for(let p=el.parentElement;p;p=p.parentElement){const r=p.getBoundingClientRect(),s=getComputedStyle(p);if(/(auto|scroll|hidden|clip)/.test(s.overflowX)&&(b.left<r.left-1||b.right>r.right+1))fail.push('x');if(/(auto|scroll|hidden|clip)/.test(s.overflowY)&&(b.top<r.top-1||b.bottom>r.bottom+1))fail.push('y')}
    return fail
  }),[])
}
try {
  await context.route(base + '/api/**',async route=>{
    const r=route.request(),u=new URL(r.url()),p=u.pathname
    let body={},status=200
    if(p.endsWith('/config')) body={configured:true,corpId:'test',clientId:'test'}
    else if(p==='/api/identity/v1/me') body={name:'测试用户',sessionId:'identity-test'}
    else if(p.endsWith('/tickets')) body={ticket:'test'}
    else if(p==='/api/v1/auth/identity/access') body={state:'unregistered'}
    else if(p.includes('/auth/')) { body={id:'actor',name:'测试用户',identitySessionId:'identity-test',status:'active',roles:[role],capabilities:caps}; if(p.endsWith('/access'))body={state:'allowed',member:body} }
    else if(p.endsWith('/management/usage')) {
      if(mode==='error'){await route.abort();return} body=summary
    } else if(p.endsWith('/management/jobs')){
      queries.push(Object.fromEntries(u.searchParams));body={items:u.searchParams.get('taskId')==='empty'?[]:[job],total:u.searchParams.get('taskId')==='empty'?0:41,page:Number(u.searchParams.get('page')||1),pageSize:20}
    } else if(p.endsWith('/management/settings')){
      if(r.method()==='PATCH'){
        writes++; const draft=r.postDataJSON(); assert.equal('autoCleanup' in draft,false);assert.ok(Object.values(draft.defaults).every(v=>v===null||v==='s1'),'表单标记不能写入API')
        if(mode==='conflict'){settings.version++;status=409}
        else {settings={...settings,...draft,version:settings.version+1};if(mode==='unknown'){await route.abort();return}}
      }
      body=settings
    } else if(p.endsWith('/management/skills')){
      assert.equal(r.method(),'GET')
      if(mode==='skill-error'){await route.abort();return}
      body={items:skills}
    }
    else throw Error('Unexpected '+p)
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
  })
  for(const r of ['operator','operator_manager','designer','design_manager','super_admin']){
    role=r;caps=r==='super_admin'?[...allCaps]:['stats.read'];await go('usage')
    await page.getByRole('heading',{name:'任务与执行统计',exact:true}).waitFor()
    await page.getByText('真实范围作业',{exact:true}).waitFor()
    assert.equal(await page.getByRole('menuitem',{name:'系统配置',exact:true}).count(),r==='super_admin'?1:0)
    if(r!=='super_admin'){await go('settings');await page.getByText('暂无此管理页面权限',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'保存配置',exact:true}).count(),0)}
  }
  await go('monitor');await page.getByText('真实范围作业',{exact:true}).waitFor()
  await page.getByPlaceholder('开始时间',{exact:true}).fill('2026-10-01 00:00:00');await page.getByPlaceholder('开始时间',{exact:true}).press('Enter')
  await page.getByPlaceholder('结束时间',{exact:true}).fill('2026-10-31 23:59:59');await page.getByPlaceholder('结束时间',{exact:true}).press('Enter')
  await page.getByRole('button',{name:'应用筛选',exact:true}).click();await page.waitForResponse(r=>r.url().includes('/management/jobs?')&&r.url().includes('from='));assert.ok(queries.at(-1).from);assert.ok(queries.at(-1).to)
  await page.locator('.el-pager').getByText('2',{exact:true}).click();await page.waitForResponse(r=>r.url().includes('/management/jobs?')&&r.url().includes('page=2'))
  await page.getByRole('textbox',{name:'任务 ID',exact:true}).fill('empty');await page.getByRole('button',{name:'应用筛选',exact:true}).click()
  await page.getByText('暂无符合条件的执行作业',{exact:true}).waitFor();assert.equal(queries.at(-1).page,'1');await unclipped(page.getByText('暂无符合条件的执行作业',{exact:true}))
  mode='error';await page.getByRole('button',{name:'刷新统计',exact:true}).click();await page.getByText('服务连接失败，请稍后重试',{exact:true}).waitFor();mode=''
  await go('settings');await page.getByRole('button',{name:'保存配置',exact:true}).waitFor()
  for (const name of ['整套分析默认 Skill','按 SKU 生图默认 Skill','单图返工默认 Skill']) {
    const select = page.locator('.el-select').filter({has:page.getByRole('combobox',{name,exact:true})})
    const label = select.locator('.el-select__selected-item').filter({hasText:'内置协议 Skill'})
    await label.waitFor({state:'visible'}); assert.equal(await label.innerText(),'内置协议 Skill'); await unclipped(label)
  }
  assert.ok((await page.locator('.hx-footnote[role="status"]').innerText()).includes('当前配置已保存'))
  await page.getByRole('spinbutton',{name:'任务并发上限',exact:true}).fill('3');await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText('配置已保存',{exact:true}).waitFor();assert.equal(settings.concurrency,3)
  await page.reload();await page.getByRole('spinbutton',{name:'任务并发上限',exact:true}).waitFor();assert.equal(await page.getByRole('spinbutton',{name:'任务并发上限',exact:true}).inputValue(),'3')
  mode='conflict';await page.getByRole('spinbutton',{name:'任务并发上限',exact:true}).fill('2');await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText('配置已变化，已刷新版本并保留草稿；请核对后保存',{exact:true}).waitFor();assert.equal(await page.getByRole('spinbutton',{name:'任务并发上限',exact:true}).inputValue(),'2')
  mode='';await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText('当前配置已保存',{exact:false}).waitFor();assert.equal(settings.concurrency,2)
  await go('skills');await page.getByText('暂无已安装 Skill',{exact:true}).waitFor()
  assert.equal(await page.getByRole('button',{name:'添加 Skill',exact:true}).count(),0)
  skills=[{id:'s1',name:'layout',displayName:'沃尔玛新品主图 · 原版',description:'完整说明：'+ '按真实参考图制作。'.repeat(60)},{id:'s2',name:'layout-new',displayName:'沃尔玛新品主图 · 新版（9.27）',description:'新版差异描述'}]
  await page.getByRole('button',{name:'刷新 Skill',exact:true}).click();await page.getByText(skills[1].displayName,{exact:true}).waitFor()
  assert.equal(await page.getByRole('columnheader').count(),2)
  await page.getByRole('textbox',{name:'搜索 Skill',exact:true}).fill('新版差异');await page.getByText(skills[1].displayName,{exact:true}).waitFor();assert.equal(await page.getByText(skills[0].displayName,{exact:true}).count(),0)
  await page.getByRole('textbox',{name:'搜索 Skill',exact:true}).fill('不匹配');await page.getByText('暂无匹配的 Skill，请调整搜索',{exact:true}).waitFor()
  await page.getByRole('textbox',{name:'搜索 Skill',exact:true}).fill('')
  mode='skill-error';await page.getByRole('button',{name:'刷新 Skill',exact:true}).click();await page.getByText('服务连接失败，请稍后重试',{exact:true}).waitFor();assert.equal(await page.getByText('暂无已安装 Skill',{exact:true}).count(),0)
  mode='';await page.getByRole('button',{name:'刷新 Skill',exact:true}).click();await page.getByText(skills[0].displayName,{exact:true}).waitFor()
  await page.setViewportSize({width:390,height:844});await unclipped(page.getByRole('button',{name:'刷新 Skill',exact:true}));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))
  const longDescription = page.getByText(skills[0].description,{exact:true})
  assert.equal(await longDescription.innerText(),skills[0].description)
  assert.deepEqual(await longDescription.evaluate(el=>{const failures=[];for(let p=el;p&&p.tagName!=='TABLE';p=p.parentElement){if(p.scrollHeight>p.clientHeight+1&&getComputedStyle(p).overflowY==='hidden')failures.push(p.tagName)}return failures}),[])
  await mkdir('../../output/playwright/delete-skills',{recursive:true});await page.screenshot({path:'../../output/playwright/delete-skills/skills-long-description-mobile.png',fullPage:true,animations:'disabled'})
  await page.setViewportSize({width:1280,height:900})
  await go('settings');await page.getByRole('combobox',{name:'整套分析默认 Skill',exact:true}).press('Enter');await page.getByRole('option',{name:'沃尔玛新品主图 · 原版',exact:true}).click();const savedSkill=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/management/settings'));await page.getByRole('button',{name:'保存配置',exact:true}).click();await savedSkill;assert.equal(settings.defaults.analysis,'s1')
  await page.getByRole('combobox',{name:'整套分析默认 Skill',exact:true}).press('Enter');await page.getByRole('option',{name:'内置协议 Skill',exact:true}).click()
  await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/management/settings'));assert.equal(settings.defaults.analysis,null)
  await page.setViewportSize({width:390,height:844});await unclipped(page.getByRole('button',{name:'保存配置',exact:true}));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))
  caps=['stats.read'];await page.getByRole('button',{name:'刷新配置',exact:true}).click();await page.locator('.hx-page').filter({hasText:/工作流任务|暂无此功能权限/}).first().waitFor();assert.equal(await page.getByRole('button',{name:'保存配置',exact:true}).count(),0)
  assert.deepEqual(errors,[]);console.log('PASS management: five roles, scope gates, filters/page/empty/error, settings persistence/409, Skill read-only/search/empty/error/default, narrow viewport, revoke')
}finally{await context.close();await browser.close()}
