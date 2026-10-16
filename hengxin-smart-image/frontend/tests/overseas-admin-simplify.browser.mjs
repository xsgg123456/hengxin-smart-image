import assert from 'node:assert/strict'
import {mkdir} from 'node:fs/promises'
await mkdir('../../output/playwright/admin-simplify',{recursive:true})
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const base=process.env.IDENTITY_UI_URL||'http://127.0.0.1:3026',browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage(),queries=[]
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname))
const archive={id:'a',taskId:'t',sourceDeleted:false,productName:'手机壳',brand:'Hengxin',platform:'Amazon',skus:[{code:'SKU-ONE'}],pictureCount:1,createdAt:'2026-10-15'}
const picture={id:'p',name:'成品.png',sku:'SKU-ONE',width:1,height:1,contentType:'image/png',sizeBytes:68,url:'/api/overseas/v1/archives/a/pictures/p/content'}
const members=[{id:'a',name:'设计甲'},{id:'b',name:'设计乙'}],button=name=>page.getByRole('button',{name,exact:true})
let role='design_manager',fault=false,operatorFault=false
const errors=[],unexpected=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000)
try{
await context.route('**/*',async route=>{
 const u=new URL(route.request().url()),p=u.pathname;let body={},status=200
 if(['api.iconify.design','api.unisvg.com','api.simplesvg.com'].includes(u.hostname)){await route.fulfill({contentType:'application/json',body:'{}'});return}
 if(u.origin!==base&&!['data:','blob:'].includes(u.protocol)){unexpected.push(route.request().url());await route.abort();return}
 if(!p.startsWith('/api/'))return route.continue()
 if(p.endsWith('/config'))body={configured:true,corpId:'test',clientId:'test'}
 else if(p==='/api/identity/v1/me')body={name:'测试',sessionId:'identity-test'}
 else if(p.endsWith('/tickets'))body={ticket:'test'}
 else if(p==='/api/v1/auth/identity/access')body={state:'unregistered'}
 else if(p.includes('/auth/')){body={id:'a',name:'测试',identitySessionId:'identity-test',status:'active',roles:[role],capabilities:['stats.read','task.read']};if(p.endsWith('/access'))body={state:'allowed',member:body}}
 else if(p.endsWith('/management/operators')){body={items:members};if(operatorFault)status=500}
 else if(p.endsWith('/usage')||p.endsWith('/jobs')){
 queries.push({path:p,...Object.fromEntries(u.searchParams)});const list=members.filter(m=>!u.searchParams.get('memberId')||m.id===u.searchParams.get('memberId'))
 body=p.endsWith('/usage')?{jobs:list.length,queued:0,running:0,uncertain:0,succeeded:list.length,failed:0,cancelled:0,generationImages:list.length,revisionImages:0}:{items:list.map(m=>({id:m.id,taskId:'t',taskName:'任务'+m.id,operatorId:m.id,operatorName:m.name,kind:'generation',status:'succeeded',executionCount:1,imageCount:1,createdAt:'2026-10-15',startedAt:null,completedAt:null,error:null})),total:u.searchParams.get('memberId')?list.length:41,page:Number(u.searchParams.get('page')||1),pageSize:20}
 }else if(p.endsWith('/archives')){queries.push({path:p,...Object.fromEntries(u.searchParams)});const q=(u.searchParams.get('search')||'').toLowerCase(),items=[archive].filter(a=>[a.productName,a.brand,a.skus[0].code].some(v=>v.toLowerCase().includes(q)));body={items,total:items.length?21:0,page:Number(u.searchParams.get('page')||1),pageSize:20};if(fault)status=500}
 else if(p==='/api/overseas/v1/archives/a')body={...archive,pictures:[picture]}
 else if(p===picture.url){await route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQmQAAAAASUVORK5CYII=','base64')});return}
 else {unexpected.push(p);await route.abort();return}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
})
await page.goto(base+'/#/overseas/admin/usage');await page.getByText('任务a',{exact:true}).waitFor();await page.getByText('任务b',{exact:true}).waitFor();assert.ok((await page.locator('body').innerText()).includes('海外全员（默认）'));assert.equal(await page.getByText(/Token|费用/).count(),0)
await page.locator('.el-pagination .btn-next').click();await page.waitForResponse(r=>r.url().includes('/jobs?')&&r.url().includes('page=2'));
await page.getByRole('combobox',{name:'执行操作者'}).click();await page.getByRole('option',{name:'设计乙',exact:true}).click();await page.getByText('任务a',{exact:true}).waitFor({state:'hidden'});await page.getByText('任务b',{exact:true}).waitFor();for(const endpoint of ['/usage','/jobs'])assert.equal(queries.filter(q=>q.path.endsWith(endpoint)).at(-1).memberId,'b');assert.equal(queries.filter(q=>q.path.endsWith('/jobs')).at(-1).page,'1')
await page.getByRole('combobox',{name:'执行操作者'}).click();await page.getByRole('option',{name:'全部人员',exact:true}).click();await page.getByText('任务a',{exact:true}).waitFor();assert.equal(queries.filter(q=>q.path.endsWith('/jobs')).at(-1).page,'1');assert.equal(queries.filter(q=>q.path.endsWith('/jobs')).at(-1).memberId,undefined);await page.screenshot({path:'../../output/playwright/admin-simplify/stats-desktop.png',fullPage:true});
await page.goto(base+'/#/overseas/admin/monitor');await page.getByText('任务a',{exact:true}).waitFor();operatorFault=true;await page.reload();await button('重试人员列表').waitFor();operatorFault=false;await button('重试人员列表').click();await button('重试人员列表').waitFor({state:'hidden'})
role='designer';await page.reload();await page.getByText('任务a',{exact:true}).waitFor();assert.ok((await page.locator('body').innerText()).includes('当前角色可见范围'))
await page.goto(base+'/#/overseas/archive');await button('下载整套成品').waitFor();assert.equal(await page.getByRole('textbox').count(),1)
const search=page.getByRole('textbox',{name:'搜索成品'})
for(const q of ['手机','Hengxin','SKU-ONE']){const response=page.waitForResponse(r=>r.url().includes('/archives?')&&decodeURIComponent(r.url()).includes(q));await search.fill(q);await response;await button('下载整套成品').waitFor();assert.deepEqual(Object.keys(queries.at(-1)).sort(),['page','pageSize','path','search'])}
await page.locator('.el-pagination .btn-next').click();await page.waitForResponse(r=>r.url().includes('page=2'));await search.fill('无匹配');await page.getByText('暂无匹配成品；设计归档后的图片会显示在这里').waitFor();assert.equal(queries.at(-1).page,'1');await button('重置筛选').click();await button('下载整套成品').waitFor();assert.equal(queries.at(-1).search,undefined)
fault=true;await button('刷新成品').click();await page.locator('.el-alert--error').waitFor();fault=false;await button('刷新成品').click();await button('下载整套成品').waitFor()
await page.screenshot({path:'../../output/playwright/admin-simplify/archive-desktop.png',fullPage:true});
await page.setViewportSize({width:390,height:844});await page.waitForTimeout(500)
for(const el of [search,button('重置筛选'),button('刷新成品')]){await el.scrollIntoViewIfNeeded();assert.deepEqual(await el.evaluate(el=>{const b=el.getBoundingClientRect(),out=[];for(let p=el.parentElement;p;p=p.parentElement){const r=p.getBoundingClientRect(),s=getComputedStyle(p);if(/auto|scroll|hidden|clip/.test(s.overflowX)&&(b.left<r.left-1||b.right>r.right+1))out.push('x');if(/auto|scroll|hidden|clip/.test(s.overflowY)&&(b.top<r.top-1||b.bottom>r.bottom+1))out.push('y')}return out}),[])}
await page.screenshot({path:'../../output/playwright/admin-simplify/archive-mobile.png',fullPage:true});
assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);console.log('PASS all-member scope without members.manage, operator filter summary/list, monitor, operator retry, ordinary scope, unified search three fields/reset/page/empty/error/mobile clipping')
}finally{await browser.close()}
