import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/playwright/api-image-edit-modes')
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
const apiTask = { id: 'fixture-api', name: '标注隔离验收', prompt: '保持结构', created: time, status: 'succeeded', operator: '隔离测试', batch: {current:1,total:1,running:0}, material:pic(3),events:[],error:null,metrics:{requestCount:1,retryCount:0,elapsedSeconds:3},items:[{id:'item-1',position:1,source:pic(4),state:'succeeded',retries:0,nextAttemptAt:null,result:pic(2),error:null,currentVersion:2,versions:[1,2].map(number=>({number,kind:number===2?'image_edit':'generation',picture:pic(number),created:time,operator:'隔离测试',text:'',annotation:null,baseVersion:null})),revision:null}] }
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
  await new Promise(resolve => setTimeout(resolve, 700)); const raw=req.postDataBuffer(), signature=Buffer.from([137,80,78,71,13,10,26,10]), start=raw.indexOf(signature)
  assert.ok(start>=0,'Uploaded multipart contains PNG'); const size=[raw.readUInt32BE(start+16),raw.readUInt32BE(start+20)];assert.deepEqual(size,[790,1500]);uploads.push({path:p,size});body=pic(90+uploads.length)
 }
 else if(p.includes('/files/') && req.method()==='DELETE') return route.fulfill({status:204})
 else if(p.endsWith('/revise')||p.endsWith('/rounds')) {
  requests.push({path:p,key:req.headers()['idempotency-key'],body:req.postData()})
  if(conflict)return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({code:'VERSION_CONFLICT',message:'当前版本已更新，请重新打开修改'})})
  if(requests.filter(r=>r.path===p).length===1)return route.abort('failed')
  body={taskId:apiTask.id}
 }
 else if(p.endsWith('/status'))body={enabled:true,paused:false,reason:null}
 else if(p==='/api/v1/api-image-edits/tasks/fixture-api')body=apiTask
 else if(p==='/api/v1/api-image-edits/tasks')body={items:[{id:apiTask.id,name:apiTask.name,created:apiTask.created,status:apiTask.status,operator:apiTask.operator,batch:apiTask.batch,cover:apiTask.items[0].source,counts:{total:1,success:1,failed:0,uncertain:0}}],total:1,page:1,pageSize:20}
 else { errors.push('Unmocked API: '+req.method()+' '+p); return route.fulfill({status:501,contentType:'application/json',body:'{}'}) }
 return route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
})
const d = page.getByRole('dialog', {name:/修改第 1 张图片/})
const confirmation = page.getByRole('dialog', {name:'确认本次修改内容',exact:true})
const field = () => d.getByRole('textbox',{name:'整体补充要求'})
const radio = kind => d.getByRole('radio',{name:kind,exact:true})
const capture = name => page.screenshot({path:path.join(output,name+'.png'),animations:'disabled'})
async function switchMode(name) { await d.getByText(name,{exact:true}).click(); assert.equal(await radio(name).isChecked(),true); await d.locator('svg[role="img"]').waitFor(); await d.locator('.picture-area .el-loading-mask').waitFor({state:'hidden'}); }
async function mark() {
 const svg=d.locator('svg[role="img"]'); const b=await svg.boundingBox(); assert.ok(b)
 await page.mouse.move(b.x+b.width*.48,b.y+b.height*.42);await page.mouse.down()
 await page.mouse.move(b.x+b.width*.62,b.y+b.height*.55,{steps:8});await page.mouse.up()
 await d.getByRole('textbox',{name:'标注 1 修改意见',exact:true}).fill('只调整这里的物体，不修改文字')
}
try {
 await page.goto(base+'#/api-image-edits/records?task=fixture-api')
 await page.getByRole('button',{name:'修改这张',exact:true}).click()
 await d.locator('svg[role="img"]').waitFor()
 assert.equal(await radio('图片修改').isChecked(),true)
 assert.equal(await field().inputValue(),'')
 await d.getByRole('button',{name:'预览提交内容',exact:true}).click()
 await d.getByText('请填写修改意见，说明标注位置需要如何调整',{exact:true}).waitFor()
 await d.getByRole('button',{name:'查看固定提示词',exact:true}).click()
 const fixed=page.getByRole('dialog',{name:'图片修改 · 固定提示词',exact:true})
 assert.match(await fixed.innerText(),/不修改任何文字内容/)
 assert.doesNotMatch(await fixed.innerText(),/手机|摄像头/)
 await fixed.getByRole('button',{name:'返回修改',exact:true}).click();await fixed.waitFor({state:'hidden'})
 await field().fill('只调整图片物体的颜色')
 await mark()
 await switchMode('文字修改')
 assert.equal(await field().inputValue(),'')
 assert.equal(await d.locator('.annotation-mark').count(),0)
 await field().fill('只将标题改为新的文字')
 await d.getByText('上传已有标注图',{exact:true}).click()
 await d.locator('input[type=file]').setInputFiles({name:'text-mark.png',mimeType:'image/png',buffer:original})
 await d.getByRole('button',{name:'移除标注图',exact:true}).waitFor()
 await switchMode('图片修改')
 assert.equal(await field().inputValue(),'只调整图片物体的颜色')
 assert.equal(await d.locator('.annotation-mark').count(),1)
 assert.equal(await d.getByRole('radio',{name:'直接标注',exact:true}).isChecked(),true)
 await switchMode('文字修改')
 assert.equal(await field().inputValue(),'只将标题改为新的文字')
 await d.getByRole('button',{name:'移除标注图',exact:true}).waitFor()
 await d.getByRole('button',{name:'移除标注图',exact:true}).click()
 await d.getByText('直接标注',{exact:true}).click()
 await switchMode('图片修改')
 checks.push('两种意见、直接标注和上传标注草稿隔离并保留')
 await d.getByRole('button',{name:'预览提交内容',exact:true}).click()
 await confirmation.waitFor()
 assert.equal(await radio('图片修改').isDisabled(),true);assert.equal(await radio('文字修改').isDisabled(),true)
 await confirmation.locator('summary').click()
 assert.match(await confirmation.innerText(),/图片修改/)
 assert.doesNotMatch(await confirmation.innerText(),/只将标题改为新的文字/)
 await capture('image-confirmation')
 const uploadResponse = page.waitForResponse(r=>r.url().endsWith('/files') && r.request().method()==='POST')
 await confirmation.getByRole('button',{name:'确认提交修改',exact:true}).click()
 assert.equal(await radio('文字修改').isDisabled(),true)
 await uploadResponse
 await d.getByText(/受理结果尚未确认/).waitFor()
 assert.equal(requests.length,1);assert.equal(uploads.length,1)
 const first=JSON.parse(requests[0].body)
 assert.equal(first.kind,'image_edit');assert.equal(first.baseVersion,2);assert.ok(first.annotationFileId)
 assert.match(first.prompt,/不修改任何文字内容/);assert.doesNotMatch(first.prompt,/只将标题改为新的文字/)
 assert.equal(await radio('文字修改').isDisabled(),true)
 await d.getByRole('button',{name:'关闭',exact:true}).click();await d.waitFor({state:'hidden'})
 await page.reload()
 await page.getByRole('button',{name:'确认原修改请求',exact:true}).click()
 await d.waitFor();assert.equal(await radio('图片修改').isChecked(),true)
 assert.equal(await radio('文字修改').isDisabled(),true)
 await d.getByRole('button',{name:'确认原修改请求',exact:true}).click();await d.waitFor({state:'hidden'})
 assert.equal(requests.length,2);assert.deepEqual(requests[0],requests[1]);assert.equal(uploads.length,1)
 checks.push('图片真实API请求与未知响应重开确认不改变类型、提示词、标注和幂等键')
 await page.getByRole('button',{name:'修改这张',exact:true}).click();await d.waitFor()
 await switchMode('文字修改')
 await field().fill('只修改指定文字')
 await d.getByRole('button',{name:'预览提交内容',exact:true}).click();await confirmation.waitFor()
 await confirmation.getByRole('button',{name:'确认提交修改',exact:true}).click();await d.waitFor({state:'hidden'})
 const textRequest=JSON.parse(requests[2].body)
 assert.equal(textRequest.kind,'text_edit');assert.equal(textRequest.annotationFileId,undefined)
 assert.match(textRequest.prompt,/仅替换用户明确指定的文字内容/);assert.doesNotMatch(textRequest.prompt,/只调整图片物体的颜色/)
 checks.push('文字真实API请求不携带图片模式意见和标注')
 for(const [width,height] of [[1920,911],[1280,800],[600,900]]) {
  await page.setViewportSize({width,height});await page.getByRole('button',{name:'修改这张',exact:true}).click()
  await d.locator('svg[role="img"]').waitFor();await d.locator('.picture-area .el-loading-mask').waitFor({state:'hidden'});await capture('editor-'+width)
  const button=d.getByRole('button',{name:'预览提交内容',exact:true});await button.scrollIntoViewIfNeeded()
  const rect=await button.boundingBox();assert.ok(rect && rect.x>=0 && rect.x+rect.width<=width && rect.y>=0 && rect.y+rect.height<=height)
  await capture('footer-'+width)
  await d.getByRole('button',{name:'关闭',exact:true}).click();await d.waitFor({state:'hidden'})
 }
 checks.push('1920/1280/600视口提交操作可见可达')
 assert.deepEqual(errors,[]);assert.ok(blockedExternal.every(origin=>['https://api.iconify.design','https://api.unisvg.com','https://api.simplesvg.com'].includes(origin)))
 await writeFile(path.join(output,'checks.json'),JSON.stringify({checks,requests,uploads,errors,blockedExternal},null,2))
 console.log('API_IMAGE_EDIT_MODES_BROWSER_PASS',checks)
} finally { await browser.close() }
