import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/playwright/annotation-workspace')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], blockedExternal = [], checks = [], downloads = [], uploads = [], requests = []
page.setDefaultTimeout(15000); page.on('pageerror', e => errors.push(e.message))
// Fresh browser context; no production backend calls, files or paid generation.
const png = async (w, h) => Buffer.from(await page.evaluate(([w,h]) => { const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');x.fillStyle='#ddd2bf';x.fillRect(0,0,w,h);x.fillStyle='#226677';x.fillRect(w/4,h/4,w/2,h/2);return c.toDataURL().split(',')[1] }, [w,h]), 'base64')
let original = await png(790,1500); const thumbnail = await png(79,150)
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`
const pic = n => ({ fileId: uuid(n), name: `v${n}.png`, url: '/fixture/thumb.png' })
const time = '2026-09-24T10:00:00Z'
const apiTask = { id: 'fixture-api', name: '标注隔离验收', prompt: '保持结构', created: time, status: 'succeeded', operator: '隔离测试', batch: {current:1,total:1,running:0}, material:pic(3),events:[],error:null,metrics:{requestCount:1,retryCount:0,elapsedSeconds:3},items:[{id:'item-1',position:1,source:pic(4),state:'succeeded',retries:0,nextAttemptAt:null,result:pic(2),error:null,currentVersion:2,versions:[1,2].map(number=>({number,picture:pic(number),created:time,operator:'隔离测试',text:'',annotation:null,baseVersion:null})),revision:null}] }
const cliTask = { id:'fixture-cli',name:'CLI标注隔离验收',mode:'wallpaper',template:'测试模板',skillVersionId:'skill-1',ownerId:'browser-user',sessionId:'session-1',state:'待查看',progress:100,images:[pic(2)],sources:[pic(3)],feedback:[],time,archived:false,currentRoundId:'round-1',executionSource:'cli' }
const cliDetail = {task:cliTask,slots:[{slot:0,versions:[1,2].map(n=>({...pic(n),id:'version-'+n,version:n,roundId:'round-1',createdAt:time})),currentVersionId:'version-2',error:null}],rounds:[],executionControl:{canRevise:true,canRetry:false,blockedReason:null}}
let failDownload = false, conflict = false
await context.route('**/*', async route => {
 const req=route.request(), u=new URL(req.url()), p=u.pathname
 if (u.origin!==new URL(base).origin) { blockedExternal.push(u.origin); return route.abort() }
 if(p.startsWith('/fixture/')) return route.fulfill({contentType:'image/png',body:thumbnail})
 if(!p.startsWith('/api/')) return route.continue()
 let body
 if(p==='/api/v1/auth/me') body={id:'browser-user',name:'隔离测试',role:'super_admin',status:'active'}
 else if(p.endsWith('/content')) { downloads.push(p+u.search); if(failDownload){failDownload=false;return route.fulfill({status:503})}return route.fulfill({contentType:'image/png',body:original}) }
 else if(p.endsWith('/files')&&req.method()==='POST') {
  const raw=req.postDataBuffer(), signature=Buffer.from([137,80,78,71,13,10,26,10]), start=raw.indexOf(signature)
  assert.ok(start>=0,'Uploaded multipart contains PNG'); const size=[raw.readUInt32BE(start+16),raw.readUInt32BE(start+20)];assert.deepEqual(size,[790,1500]);uploads.push({path:p,size});body=pic(90+uploads.length)
 }
 else if(p.endsWith('/revise')||p.endsWith('/rounds')) {
  requests.push({path:p,key:req.headers()['idempotency-key'],body:req.postData()})
  if(conflict)return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({code:'VERSION_CONFLICT',message:'当前版本已更新，请重新打开修改'})})
  if(requests.filter(r=>r.path===p).length===1)return route.abort('failed')
  body=p.endsWith('/revise')?{taskId:apiTask.id}:{taskId:cliTask.id,roundId:'round-2',state:'排队中'}
 }
 else if(p.endsWith('/status'))body={enabled:true,paused:false,reason:null}
 else if(p==='/api/v1/api-image-edits/tasks/fixture-api')body=apiTask
 else if(p==='/api/v1/api-image-edits/tasks')body={items:[{id:apiTask.id,name:apiTask.name,created:apiTask.created,status:apiTask.status,operator:apiTask.operator,batch:apiTask.batch,cover:apiTask.items[0].source,counts:{total:1,success:1,failed:0,uncertain:0}}],total:1,page:1,pageSize:20}
 else if(p.endsWith('/execution'))body={taskId:cliTask.id,roundId:'round-1',status:'succeeded',source:'cli',diagnosticId:null,stage:'completed',label:'已完成',startedAt:time,finishedAt:time,updatedAt:time,lastActivityAt:time,totalImages:1,detectedImages:1,legacy:false,events:[],failure:null}
 else if(p==='/api/v1/tasks/fixture-cli')body=cliDetail
 else if(p==='/api/v1/tasks')body={items:[cliTask],total:1,page:1,pageSize:20,stats:{total:1,processing:0,ready:1,archived:0}}
 else { errors.push('Unmocked API: '+req.method()+' '+p); return route.fulfill({status:501,contentType:'application/json',body:'{}'}) }
 return route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
})
const dialog = () => page.getByRole('dialog',{name:/修改第 1 张图片/})
const capture = name => page.screenshot({path:path.join(output,name+'.png'),animations:'disabled'})
async function drag(x,y,dx,dy){await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});await page.mouse.up()}
const measure = svg => svg.evaluate(el => { const m=el.getScreenCTM(), b=el.getBoundingClientRect(); return { a:m.a,d:m.d,e:m.e,f:m.f,x:b.x,y:b.y,width:b.width,height:b.height,view:el.getAttribute('viewBox') } })
const stable = (a,b,label) => { for(const k of ['a','d','e','f','x','y','width','height']) assert.ok(Math.abs(a[k]-b[k])<.1,`${label} ${k}: ${a[k]} -> ${b[k]}`) }
const results=[]
try {
 for(const [w,h] of (process.env.ANNOTATION_SMALL_ONLY ? [] : [[800,800],[790,1500]])) for(const [vw,vh] of [[1920,911],[1280,720],[600,800],[390,844]]) for(const tool of ['框选问题','画笔圈注']) {
  await page.setViewportSize({width:vw,height:vh});original=await png(w,h)
  await page.goto(base+'#/api-image-edits/records?task=fixture-api');await page.reload();await page.getByRole('button',{name:'修改这张',exact:true}).click()
  const d=dialog(),svg=d.locator('svg[role="img"]');await svg.waitFor();await page.waitForTimeout(400)
  await d.getByRole('button',{name:tool,exact:true}).click();await d.getByRole('button',{name:'放大',exact:true}).click()
  let before=await measure(svg),start={x:before.e+w*.42*before.a,y:before.f+h*.40*before.d};await drag(start.x,start.y,100,80);let after=await measure(svg);const firstBefore={...before}
  stable(before,after,`首笔 ${w} ${vw} ${tool}`);assert.equal(await svg.locator('.annotation-mark').count(),1)
  const geometry=await svg.locator('.annotation-mark').first().evaluate(el=> {const p=el.querySelector('path'),r=el.querySelector('rect');return p?p.getAttribute('d'):[+r.getAttribute('x'),+r.getAttribute('y')]})
  if(Array.isArray(geometry)){assert.ok(Math.abs(geometry[0]-w*.42)<1);assert.ok(Math.abs(geometry[1]-h*.4)<1)}
  else {const values=geometry.split(' ');assert.ok(Math.abs(+values[1]-w*.42)<1);assert.ok(Math.abs(+values[2]-h*.4)<1)}
  await drag(start.x+40,start.y+35,45,40);assert.equal(await svg.locator('.annotation-mark').count(),2)
  await d.getByRole('textbox',{name:'标注 1 修改意见',exact:true}).fill('第一处\n'.repeat(30));stable(before,await measure(svg),'意见输入')
  await d.locator('aside').evaluate(el=>{el.scrollTop=el.scrollHeight});stable(before,await measure(svg),'右栏滚动')
  await d.getByRole('button',{name:'撤销',exact:true}).click();stable(before,await measure(svg),'撤销')
  if(tool==='框选问题') {
    await d.getByRole('button',{name:'适应窗口',exact:true}).click();before=await measure(svg);
    await d.locator('.mark-note').first().click();const rect=svg.locator('.annotation-mark').first().locator(':scope > rect').first();
    for(const direction of ['nw','e','se']) {const handle=svg.locator('[data-resize="'+direction+'"]'),hb=await handle.boundingBox(),old=await rect.getAttribute('width');await drag(hb.x+hb.width/2,hb.y+hb.height/2,-12,direction==='e'?0:-12);assert.notEqual(await rect.getAttribute('width'),old);stable(before,await measure(svg),'手柄调整')} 
  }
  await d.locator('aside').evaluate(el=>{el.scrollTop=0});await d.getByText('上传已有标注图',{exact:true}).click();stable(before,await measure(svg),'模式切换');await d.getByText('直接标注',{exact:true}).click()
  await d.getByRole('button',{name:'原图 100%',exact:true}).click();let actual=await measure(svg);assert.ok(Math.abs(actual.a-1)<.001,`真实100% ${w} ${vw} ${tool}: ${actual.a}`)
  let b=await svg.boundingBox(),anchor={x:Math.round(b.x+b.width*.5+15),y:Math.round(b.y+b.height*.5+10)};let point={x:(anchor.x-actual.e)/actual.a,y:(anchor.y-actual.f)/actual.d}
  await page.mouse.move(anchor.x,anchor.y);await page.mouse.wheel(0,-120);await page.waitForTimeout(80);let zoomed=await measure(svg);assert.ok(Math.abs(zoomed.e+point.x*zoomed.a-anchor.x)<.1,'鼠标缩放锚点x');assert.ok(Math.abs(zoomed.f+point.y*zoomed.d-anchor.y)<.1,'鼠标缩放锚点y')
  await svg.evaluate(()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur()});await page.keyboard.down('Space');await page.waitForFunction(()=>getComputedStyle(document.querySelector('.annotation-stage')).cursor==='grab');await drag(anchor.x,anchor.y,-20,-15);await page.keyboard.up('Space');await page.waitForFunction(()=>getComputedStyle(document.querySelector('.annotation-stage')).cursor==='crosshair');assert.notEqual((await measure(svg)).view,zoomed.view,'空格平移')
  let previous=await measure(svg);await page.mouse.move(anchor.x,anchor.y);await page.mouse.down({button:'middle'});await page.mouse.move(anchor.x+20,anchor.y+15);await page.mouse.up({button:'middle'});assert.notEqual((await measure(svg)).view,previous.view,'中键平移')
  const count=await svg.locator('.annotation-mark').count();
  await svg.evaluate(el=>el.addEventListener('pointerdown',ev=>{el.dataset.pointer=String(ev.pointerId)},{once:true}));await page.mouse.move(anchor.x,anchor.y);await page.mouse.down();await page.mouse.move(anchor.x+35,anchor.y+20);await svg.evaluate(el=>el.dispatchEvent(new PointerEvent('pointercancel',{pointerId:Number(el.dataset.pointer),bubbles:true})));await page.mouse.up();assert.equal(await svg.locator('.annotation-mark').count(),count,'pointercancel取消');await page.mouse.move(anchor.x,anchor.y);await page.mouse.down();await page.mouse.move(anchor.x+30,anchor.y+20);await page.evaluate(()=>window.dispatchEvent(new Event('blur')));await page.mouse.up();assert.equal(await svg.locator('.annotation-mark').count(),count,'blur取消')
  await d.locator('aside').evaluate(el=>{el.scrollTop=0});let input=d.getByRole('textbox',{name:'标注 1 修改意见',exact:true});await input.fill('a');await input.press('Space');assert.equal(await input.inputValue(),'a ','输入空格')
  await d.getByRole('button',{name:'适应窗口',exact:true}).click();await capture(`${w}-${h}-${vw}-${tool==='框选问题'?'rect':'pen'}`)
  await d.getByRole('button',{name:'预览提交内容',exact:true}).click();const preview=page.getByRole('dialog',{name:'确认本次修改内容',exact:true});await preview.waitFor();const imageSize=await preview.locator('.el-image img').evaluate(async img=>{await img.decode();return [img.naturalWidth,img.naturalHeight]});assert.deepEqual(imageSize,[w,h]);await preview.getByRole('button',{name:'返回继续标注',exact:true}).click();
  results.push({image:[w,h],viewport:[vw,vh],tool,before:firstBefore,after,pass:true})
 }

 await page.setViewportSize({width:1920,height:911});original=await png(200,200);await page.goto(base+'#/api-image-edits/records?task=fixture-api');await page.reload();await page.getByRole('button',{name:'修改这张',exact:true}).click();const smallDialog=dialog(),smallSvg=smallDialog.locator('svg[role="img"]');await smallSvg.waitFor();await page.waitForTimeout(400);await smallDialog.getByRole('button',{name:'原图 100%',exact:true}).click();const small=await measure(smallSvg);assert.ok(Math.abs(small.a-1)<.001);assert.ok(Math.abs(small.e+100-small.x-small.width/2)<.1);assert.ok(Math.abs(small.f+100-small.y-small.height/2)<.1);assert.equal(await smallDialog.getByRole('button',{name:'按住拖动图片',exact:true}).isDisabled(),true);await writeFile(path.join(output,'small-image.json'),JSON.stringify({passed:true,size:[200,200],small},null,2));
 if(process.env.ANNOTATION_SMALL_ONLY){console.log('200×200 100%居中、手柄禁用：PASS');await browser.close();process.exit(0)}
 assert.deepEqual(errors,[]);assert.ok(blockedExternal.every(origin=>['https://api.iconify.design','https://api.simplesvg.com','https://api.unisvg.com'].includes(origin)))
 await writeFile(path.join(output,'measurements.json'),JSON.stringify(results,null,2));await writeFile(path.join(output,'checks.json'),JSON.stringify({passed:true,cases:results.length,errors,blockedExternal:[...new Set(blockedExternal)],checks:['API真实组件800×800/790×1500、四视口、框选/画笔首笔后笔','CTM及画布矩形在首笔、意见、滚动、撤销、模式切换恒定','重叠框内部不移动旧框、NW/E/SE手柄','实际100%与滚轮鼠标锚点','空格/中键平移、blur及pointercancel回滚、输入空格','每组真实原尺寸预览导出']},null,2));console.log(JSON.stringify({passed:true,cases:results.length,checks:'首笔/后笔/意见/滚动/模式切换无跳动；100%、滚轮锚点、空格/中键平移、blur取消、输入空格'}))
} finally { await browser.close() }
