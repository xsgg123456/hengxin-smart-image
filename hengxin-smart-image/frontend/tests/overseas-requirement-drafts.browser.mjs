// Isolated formal UI fixture. All API traffic intercepted; never connects to production.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3047'
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless:true }), context = await browser.newContext({viewport:{width:1366,height:900}}), page = await context.newPage()
const output='../../output/playwright/sku-drafts'; await mkdir(output,{recursive:true})
page.setDefaultTimeout(20000)
const errors=[], unexpected=[], creates=[]; page.on('pageerror',e=>errors.push(e.message))
const caps=['task.create','task.read','task.requirements.resubmit'], designer={id:'designer-30',name:'真实设计三十',department:'设计部'}
const blank=()=>({name:'',productName:'',brand:'',platform:'',language:'',market:'',skus:[{code:''}],designerId:''})
const fresh=()=>({id:'draft-1',version:1,fields:blank(),source:null,materials:[],imports:[],updatedAt:'2026-11-03',submitKey:'submission-key',matchedDesigner:null,lastSubmittedTaskId:null,lastSubmittedKey:null})
let draft=fresh(), mode='normal', saveFail=false, actor='actor', submitted, seq=0
const task=()=>({id:'created-task',...submitted?.body,name:submitted?.body.name||'任务',remarks:'',workflow:'studio',status:'pending_review',version:1,createdAt:'2026-11-03',updatedAt:'2026-11-03',createdBy:{id:'actor',name:'测试账号'},designer:{...designer,status:'active',eligible:true},capabilities:caps,events:[],requirementsReviews:[]})
const material=(id,kind='requirement',name=`${id}.pptx`)=>({id,kind,name,sizeBytes:30,contentType:'application/octet-stream',taskId:null,createdAt:'2026-11-03',status:'ready'})
const requirement=(id='r1')=>({id,title:`需求 ${id}`,productName:'落地灯',brandName:'OUTON',platformName:'亚马逊/Amazon',language:'英语',designerName:designer.name,matchedDesigner:designer,status:'待开始',createdAt:'2026-11-03',files:[{id:'f1',filename:'主图需求.PPTX',size:30},{id:'f2',filename:'副图需求.PPT',size:30},{id:'f3',filename:'竞品分析.xlsx',size:30},{id:'f4',filename:'规格.pdf',size:30}]})
const button=name=>page.getByRole('button',{name,exact:true}), field=label=>page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').getByText(label,{exact:true})})
async function ready(){await page.getByText('草稿已保存',{exact:true}).waitFor()}
async function lookup(sku){await page.getByRole('textbox',{name:'商品 SKU',exact:true}).fill(sku);await button('获取需求').click()}
async function unclipped(locator){await locator.scrollIntoViewIfNeeded();assert.ok(await locator.evaluate(el=>{const b=el.getBoundingClientRect();for(let p=el.parentElement;p;p=p.parentElement){const r=p.getBoundingClientRect(),s=getComputedStyle(p);if(/(auto|scroll|hidden|clip)/.test(s.overflowX)&&(b.left<r.left-1||b.right>r.right+1))return false;if(/(auto|scroll|hidden|clip)/.test(s.overflowY)&&(b.top<r.top-1||b.bottom>r.bottom+1))return false}return b.width>0&&b.height>0}))}
try{
 await context.route(`${base}/api/**`,async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname,method=req.method();let status=200,body={}
  if(p.endsWith('/config'))body={configured:true,corpId:'test',clientId:'test'}
  else if(p==='/api/identity/v1/me')body={name:'测试账号',sessionId:'identity-test'}
  else if(p.endsWith('/tickets'))body={ticket:'test'}
  else if(p==='/api/v1/auth/identity/access')body={state:'unregistered'}
  else if(p.includes('/auth/')){body={id:actor,name:'测试账号',identitySessionId:'identity-test',status:'active',roles:['super_admin'],capabilities:caps};if(p.endsWith('/access'))body={state:'allowed',member:body}}
  else if(p.endsWith('/task-designers')){const n=Number(u.searchParams.get('page'));body={items:n===1?[{id:'d1',name:'设计一',department:'设计部'}]:[designer],total:21,page:n,pageSize:20}}
  else if(p.endsWith('/requirement-source')){const sku=u.searchParams.get('sku');if(sku==='ERROR'){status=503}else{body={sku,count:sku==='MULTI'?2:sku==='EMPTY'?0:1,truncated:false,list:sku==='MULTI'?[requirement('r1'),requirement('r2')]:sku==='EMPTY'?[]:[requirement()]};if(sku==='SLOW')await new Promise(r=>setTimeout(r,800))}}
  else if(p.endsWith('/requirement-draft')){
   if(method==='PUT'){const b=req.postDataJSON();if(saveFail){status=503}else if(b.version!==draft.version){status=409}else{draft={...draft,fields:b.fields,version:draft.version+1,matchedDesigner:b.fields.designerId===designer.id?designer:null}}}
   if(method==='DELETE'){const b=req.postDataJSON();if(b.version!==draft.version){status=409}else draft={...fresh(),id:`clear-${++seq}`,version:draft.version+1}}
   body=draft
  }else if(p.endsWith('/requirement-draft/source')){
   const b=req.postDataJSON();if(b.version!==draft.version){status=409}else{
    const same=draft.source?.requirementId===b.requirementId;draft={...draft,id:same?draft.id:`source-${++seq}`,version:draft.version+1,fields:b.fields,source:{sku:b.sku,requirementId:b.requirementId},matchedDesigner:designer}
    if(!same){draft.materials=[];draft.imports=requirement().files.map((f,i)=>({id:`i${i}`,sourceFileId:f.id,filename:f.filename,size:f.size,kind:i<2?'requirement':'competitor',state:'running',progress:30,error:null,materialId:null}))}
   }body=draft
  }else if(p.includes('/requirement-draft/imports/')){const id=p.split('/imports/')[1].split('/')[0],i=draft.imports.find(i=>i.id===id);if(p.endsWith('/retry')){i.state='ready';i.progress=100;i.error=null;i.materialId=`m${id}`;draft.materials.push(material(i.materialId,i.kind,i.filename))}else{i.state='cancelled';draft.materials=draft.materials.filter(m=>m.id!==i.materialId)}draft.version++;body=draft}
  else if(p.includes('/requirement-draft/materials/')){draft.materials=draft.materials.filter(m=>m.id!==p.split('/').at(-1));draft.version++;body=draft}
  else if(p.endsWith('/materials')&&method==='POST'){assert.equal(u.searchParams.get('draftId'),draft.id);await new Promise(r=>setTimeout(r,1200));const m=material(`manual-${++seq}`,u.searchParams.get('kind'),'手动资料.txt');draft.materials.push(m);body=m}
  else if(p.endsWith('/tasks')&&method==='POST'){
   const key=req.headers()['idempotency-key'],b=req.postDataJSON();creates.push({body:b,key})
   if(!submitted){assert.equal(b.draftId,draft.id);assert.equal(b.draftVersion,draft.version);assert.equal(b.skus.length,1);submitted={body:b,key};draft={...fresh(),id:'consumed',version:draft.version+1,lastSubmittedTaskId:'created-task',lastSubmittedKey:key}}
   assert.equal(key,submitted.key);if(mode==='unknown'){await route.abort();return}body=task();status=201
  }else if(p.endsWith('/tasks/created-task/materials'))body=(submitted?.body.materialIds||[]).map(id=>({...material(id),taskId:'created-task'}))
  else if(p.endsWith('/tasks/created-task'))body=task()
  else if(p.endsWith('/tasks'))body={items:[],total:0,page:1,pageSize:20}
  else{unexpected.push(p);status=404}
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
 })
 await page.goto(`${base}/#/overseas/create`);await ready();assert.equal(await button('添加 SKU').count(),0)
 await lookup('SLOW');assert.equal(await button('清空草稿').isDisabled(),true);assert.equal(await page.locator('[data-material-kind="competitor"] input[type=file]').isDisabled(),true)
 await page.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles({name:'unconfirmed.txt',mimeType:'text/plain',buffer:Buffer.from('must not upload during lookup')});assert.equal(await page.getByText('unconfirmed.txt',{exact:true}).count(),0)
 await page.getByRole('textbox',{name:'商品 SKU',exact:true}).fill('EMPTY');await page.waitForTimeout(1000);assert.equal(await field('任务名称').locator('input').inputValue(),'');assert.equal(await button('清空草稿').isEnabled(),true)
 await lookup('MULTI');await page.getByRole('dialog',{name:'选择要导入的需求'}).waitFor();assert.equal(await button('使用这条需求').isDisabled(),true);await page.locator('.requirement-title strong').filter({hasText:'需求 r2'}).click();await button('使用这条需求').click();await page.getByText('需求已回填，可继续修改；附件正在后台自动导入。').waitFor()
 assert.equal(await field('任务名称').locator('input').inputValue(),'需求 r2');assert.equal(await button('提交图需').isDisabled(),true);assert.equal(await page.locator('[data-kind="requirement"] .import-file').count(),2);assert.equal(await page.locator('[data-kind="competitor"] .import-file').count(),2)
 await field('任务名称').locator('input').fill('最后输入持久化');await ready();await page.reload();await ready();assert.equal(await field('任务名称').locator('input').inputValue(),'最后输入持久化');assert.equal(await page.locator('.import-file').count(),4)
 draft.imports.forEach((i,n)=>{i.state=n===3?'failed':'ready';i.progress=n===3?30:100;i.error=n===3?'网络失败':null;i.materialId=n===3?null:`m${n}`;if(i.materialId)draft.materials.push(material(i.materialId,i.kind,i.filename))});await page.getByText('网络失败',{exact:true}).waitFor();await button('重试').click();await page.getByText('网络失败',{exact:true}).waitFor({state:'hidden'});await ready();assert.equal(await page.locator('.import-file').count(),4)
 await lookup('MULTI');await page.locator('.requirement-title strong').filter({hasText:'需求 r2'}).click();await button('使用这条需求').click();await button('确认回填').click();await page.getByRole('dialog',{name:'选择要导入的需求'}).waitFor({state:'hidden'});await ready();assert.equal(await page.locator('.import-file').count(),4)
 await page.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles([{name:'手动一.txt',mimeType:'text/plain',buffer:Buffer.from('one')},{name:'手动二.txt',mimeType:'text/plain',buffer:Buffer.from('two')}]);assert.equal(await button('获取需求').isDisabled(),true);assert.equal(await button('清空草稿').isDisabled(),true);await page.waitForFunction(()=>document.querySelectorAll('.import-file .file-actions').length===6);assert.equal(draft.materials.length,6);await button('获取需求').waitFor({state:'visible'});assert.equal(await button('获取需求').isEnabled(),true);assert.equal(await button('清空草稿').isEnabled(),true)
 await lookup('ERROR');await page.getByText(/查询失败/).waitFor();assert.equal(await field('任务名称').locator('input').inputValue(),'需求 r2')
 await field('任务名称').locator('input').fill('最后输入持久化');await lookup('EMPTY');await page.getByText(/未找到 SKU/).waitFor();assert.equal(await field('任务名称').locator('input').inputValue(),'最后输入持久化');assert.equal(await button('提交图需').isDisabled(),true)
 await page.getByRole('textbox',{name:'商品 SKU',exact:true}).fill('MULTI');await ready()
 saveFail=true;await field('品名').locator('input').fill('离线输入仍保留');await page.getByText('草稿保存失败',{exact:true}).waitFor();await page.reload();await page.getByText('草稿保存失败',{exact:true}).waitFor();assert.equal(await field('品名').locator('input').inputValue(),'离线输入仍保留');saveFail=false;await button('重试保存').click();await ready()
 draft={...draft,version:draft.version+1,fields:{...draft.fields,name:'其他标签更新'}};await page.getByText('草稿版本冲突',{exact:true}).waitFor();assert.equal(await field('任务名称').locator('input').inputValue(),'最后输入持久化');await button('用本地字段恢复').click();await button('确认恢复').click();await ready();assert.equal(draft.fields.name,'最后输入持久化')
 await page.getByRole('dialog',{name:'选择草稿恢复方式'}).waitFor({state:'hidden'})
 await page.screenshot({path:`${output}/desktop.png`,fullPage:true});await page.setViewportSize({width:390,height:844});await unclipped(page.locator('[data-kind="requirement"] .file-name').first());await unclipped(button('提交图需'));await page.screenshot({path:`${output}/mobile.png`,fullPage:true});await page.setViewportSize({width:1366,height:900})
 mode='unknown';await button('提交图需').click();await button('重试提交并确认结果').waitFor();assert.equal(creates.length,1);mode='normal';await button('重试提交并确认结果').click();await page.getByRole('heading',{name:'图需审核',exact:true}).waitFor();assert.equal(creates.length,2);assert.equal(creates[0].key,creates[1].key);assert.deepEqual(creates[0].body,creates[1].body);assert.equal(await page.locator('[data-material-id]').count(),6)
 await page.goto(`${base}/#/overseas/create`);await ready();assert.equal(await field('任务名称').locator('input').inputValue(),'')
 await field('任务名称').locator('input').fill('账号一私有草稿');await ready();const actorOne=structuredClone(draft);actor='actor-two';draft=fresh();await page.reload();await ready();assert.equal(await field('任务名称').locator('input').inputValue(),'');actor='actor';draft=actorOne;await page.reload();await ready();assert.equal(await field('任务名称').locator('input').inputValue(),'账号一私有草稿')
 await page.addInitScript(()=>{Storage.prototype.setItem=function(){throw new Error('quota')}});await page.reload();await ready();await field('任务名称').locator('input').fill('本地失败服务器保留');await ready();assert.equal(draft.fields.name,'本地失败服务器保留');await page.getByText('浏览器无法保存恢复副本；请等待服务器显示已保存后再离开。').waitFor()
 assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);console.log('PASS: 单SKU、多记录选择、迟到保护、4后台附件分类/恢复/去重/重试及2手动上传、空/失败态、本地恢复/配额失败、跨账号隔离、多标签冲突、窄屏、未知提交稳定幂等、审核6附件与成功清空')
}finally{await context.close();await browser.close()}
