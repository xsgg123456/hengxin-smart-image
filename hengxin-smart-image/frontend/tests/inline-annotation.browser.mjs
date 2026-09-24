import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/inline-annotation-20260924')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], blockedExternal = [], checks = [], downloads = [], uploads = [], requests = []
page.setDefaultTimeout(15000); page.on('pageerror', e => errors.push(e.message))
// Fresh browser context; no production backend calls, files or paid generation.
const png = async (w, h) => Buffer.from(await page.evaluate(([w,h]) => { const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');x.fillStyle='#ddd2bf';x.fillRect(0,0,w,h);x.fillStyle='#226677';x.fillRect(w/4,h/4,w/2,h/2);return c.toDataURL().split(',')[1] }, [w,h]), 'base64')
const original = await png(790,1500), thumbnail = await png(79,150)
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`
const pic = n => ({ fileId: uuid(n), name: `v${n}.png`, url: '/fixture/thumb.png' })
const time = '2026-09-24T10:00:00Z'
const apiTask = { id: 'fixture-api', name: '标注隔离验收', prompt: '保持结构', created: time, status: 'succeeded', operator: '隔离测试', batch: {current:1,total:1,running:0}, material:pic(3),events:[],error:null,metrics:{requestCount:1,retryCount:0,elapsedSeconds:3},items:[{id:'item-1',position:1,source:pic(4),state:'succeeded',retries:0,nextAttemptAt:null,result:pic(2),error:null,currentVersion:2,versions:[1,2].map(number=>({number,picture:pic(number),created:time,operator:'隔离测试',text:'',annotation:null,baseVersion:null})),revision:null}] }
const cliTask = { id:'fixture-cli',name:'CLI标注隔离验收',mode:'wallpaper',template:'测试模板',skillVersionId:'skill-1',ownerId:'browser-user',sessionId:'session-1',state:'待查看',progress:100,images:[pic(2)],sources:[pic(3)],feedback:[],time,archived:false,currentRoundId:'round-1',executionSource:'cli' }
const cliDetail = {task:cliTask,slots:[{slot:0,versions:[1,2].map(n=>({...pic(n),id:'version-'+n,version:n,roundId:'round-1',createdAt:time})),currentVersionId:'version-2',error:null}],rounds:[],executionControl:{canRevise:true,canRetry:false,blockedReason:null}}
let failDownload = true, conflict = false
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
 else if(p==='/api/v1/api-image-edits/tasks')body={items:[apiTask],total:1,page:1,pageSize:20}
 else if(p.endsWith('/execution'))body={taskId:cliTask.id,roundId:'round-1',status:'succeeded',source:'cli',diagnosticId:null,stage:'completed',label:'已完成',startedAt:time,finishedAt:time,updatedAt:time,lastActivityAt:time,totalImages:1,detectedImages:1,legacy:false,events:[],failure:null}
 else if(p==='/api/v1/tasks/fixture-cli')body=cliDetail
 else if(p==='/api/v1/tasks')body={items:[cliTask],total:1,page:1,pageSize:20,stats:{total:1,processing:0,ready:1,archived:0}}
 else { errors.push('Unmocked API: '+req.method()+' '+p); return route.fulfill({status:501,contentType:'application/json',body:'{}'}) }
 return route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
})
const dialog = () => page.getByRole('dialog',{name:/修改第 1 张图片/})
const capture = name => page.screenshot({path:path.join(output,name+'.png'),animations:'disabled'})
async function drag(x,y,dx,dy){await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});await page.mouse.up()}
async function annotate() {
 const d=dialog(), svg=d.locator('svg[role="img"]');await svg.waitFor()
 await page.waitForTimeout(450); const b=await svg.boundingBox();await drag(b.x+b.width*.44,b.y+b.height*.28,55,70)
 await d.getByRole('textbox',{name:'标注 1 修改意见',exact:true}).fill('修正第一处边缘')
 await d.getByRole('button',{name:'放大',exact:true}).click();await d.getByRole('button',{name:'放大',exact:true}).click()
 const before=await svg.getAttribute('viewBox'), handle=d.getByRole('button',{name:'按住拖动图片',exact:true}), h=await handle.boundingBox()
 await drag(h.x+h.width/2,h.y+h.height/2,-70,-50);assert.notEqual(await svg.getAttribute('viewBox'),before)
 assert.equal(await svg.locator('.annotation-mark').count(),1)
 await d.getByRole('button',{name:'画笔圈注',exact:true}).click();await drag(b.x+b.width*.5,b.y+b.height*.6,45,35)
 await d.getByRole('textbox',{name:'标注 2 修改意见',exact:true}).fill('修复第二处开孔')
 const penBefore=await svg.getAttribute('viewBox'), h2=await handle.boundingBox();await drag(h2.x+h2.width/2,h2.y+h2.height/2,25,20);assert.notEqual(await svg.getAttribute('viewBox'),penBefore)
 assert.equal(await svg.locator('.annotation-mark').count(),2);assert.match(await d.locator('.annotation-help').innerText(),/画笔/)
 const afterPan=await svg.boundingBox();await drag(afterPan.x+afterPan.width*.5,afterPan.y+afterPan.height*.75,25,15);assert.equal(await svg.locator('.annotation-mark').count(),3)
 await d.getByRole('button',{name:'撤销',exact:true}).click();assert.equal(await svg.locator('.annotation-mark').count(),2);assert.equal(await d.getByRole('textbox',{name:'标注 1 修改意见',exact:true}).inputValue(),'修正第一处边缘')
 await d.getByRole('textbox',{name:'整体补充要求',exact:true}).fill('保持其余设计')
}
async function submitAndRetry(kind) {
 const d=dialog();await d.getByRole('button',{name:'预览提交内容',exact:true}).click()
 const preview=page.getByRole('dialog',{name:'确认本次修改内容',exact:true});await preview.waitFor()
 assert.match(await preview.locator('pre').innerText(),/修正第一处边缘/);assert.match(await preview.locator('pre').innerText(),/修复第二处开孔/)
 await capture(kind+'-preview');await preview.getByRole('button',{name:'确认提交修改',exact:true}).click()
 const retry=d.getByRole('button',{name:kind==='api'?'确认原修改请求':'确认上次提交',exact:true});await retry.waitFor();await retry.click()
 await d.waitFor({state:'hidden'});const pair=requests.slice(-2);assert.equal(pair[0].key,pair[1].key);assert.ok(pair[0].key);assert.equal(pair[0].body,pair[1].body)
 assert.equal(uploads.length,kind==='api'?1:2)
}
try {
 await page.goto(base+'#/api-image-edits/records?task='+apiTask.id)
 await page.getByRole('button',{name:'修改这张',exact:true}).click()
 await dialog().getByRole('button',{name:'重新读取成品原图',exact:true}).click()
 await dialog().getByText(/成品原始尺寸：790 × 1500/).waitFor();await annotate();await capture('api-mixed-marks')
 await dialog().getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('button',{name:'修改这张',exact:true}).click()
 await dialog().getByRole('textbox',{name:'标注 2 修改意见',exact:true}).waitFor();assert.equal(await dialog().getByRole('textbox',{name:'标注 1 修改意见',exact:true}).inputValue(),'修正第一处边缘')
 await submitAndRetry('api');assert.equal(JSON.parse(requests[0].body).baseVersion,2)
 checks.push('API原始790×1500下载/失败重读、矩形+画笔、两工具固定手柄平移、草稿关闭重开、原尺寸PNG、预览编号意见、网络失败同key/body重试且仅上传一次')
 await page.goto(base+'#/tasks/index');await page.getByText(cliTask.name,{exact:true}).click()
 await page.locator('.hx-result-grid .el-select').click();await page.getByRole('option',{name:'v1 · 历史版本',exact:true}).click()
 await page.getByRole('button',{name:'修改这张',exact:true}).click();await dialog().getByText(/成品原始尺寸：790 × 1500/).waitFor()
 assert.match(await dialog().getAttribute('aria-label')||await dialog().innerText(),/基于 V1/)
 await dialog().getByText('上传已有标注图',{exact:true}).click();await dialog().locator('input[type="file"]').setInputFiles({name:'external.png',mimeType:'image/png',buffer:original})
 await dialog().getByRole('button',{name:'移除标注图',exact:true}).waitFor();await dialog().getByRole('button',{name:'预览提交内容',exact:true}).click()
 await dialog().getByText('请填写修改意见',{exact:false}).waitFor();assert.equal(await page.getByRole('dialog',{name:'确认本次修改内容',exact:true}).isVisible(),false)
 await dialog().getByText('直接标注',{exact:true}).click();await annotate();await submitAndRetry('cli')
 assert.equal(JSON.parse(requests.at(-1).body).baseVersionId,'version-1');assert.ok(downloads.some(p=>p==='/api/v1/files/'+uuid(1)+'/content?download=true'))
 checks.push('CLI真实任务入口指定历史V1下载、混合标注与原尺寸导出、完整编号意见、冻结历史版本及同key/body重试且仅上传一次')
 await page.goto(base+'#/api-image-edits/records?task='+apiTask.id);await page.getByRole('button',{name:'修改这张',exact:true}).click()
 await dialog().getByText(/成品原始尺寸：790 × 1500/).waitFor();await dialog().getByText('上传已有标注图',{exact:true}).click()
 await dialog().locator('input[type="file"]').setInputFiles({name:'external.png',mimeType:'image/png',buffer:original});await dialog().getByRole('button',{name:'移除标注图',exact:true}).waitFor()
 await page.setViewportSize({width:1280,height:720});await page.waitForTimeout(450)
 const footer=await dialog().locator('.el-dialog__footer').boundingBox();assert.ok(footer.y>=0&&footer.y+footer.height<=720)
 assert.ok(await dialog().locator('.annotation-editor').evaluate(el=>el.scrollHeight>=el.clientHeight));await capture('api-upload-1280x720')
 conflict=true;await dialog().getByRole('button',{name:'预览提交内容',exact:true}).click();await page.getByRole('dialog',{name:'确认本次修改内容',exact:true}).getByRole('button',{name:'确认提交修改',exact:true}).click()
 await dialog().getByText('当前版本已更新，请重新打开修改',{exact:true}).waitFor();assert.equal(await dialog().getByRole('button',{name:'确认原修改请求',exact:true}).count(),0)
 checks.push('API外部PNG选择上传与无文字预览提交、版本冲突409保持弹窗不误报受理；CLI仅上传无意见阻止预览；1280×720固定页脚可见')
 assert.deepEqual(errors,[])
 await writeFile(path.join(output,'checks.json'),JSON.stringify({passed:true,checks,downloads,uploads,requests,errors,blockedExternal},null,2));console.log(JSON.stringify({passed:true,checks},null,2))
} catch(e){await capture('failure');console.error((await page.locator('body').innerText()).slice(-3500));throw e}
finally{await context.close();await browser.close()}





