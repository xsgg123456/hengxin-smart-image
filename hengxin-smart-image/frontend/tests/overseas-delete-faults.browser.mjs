// Mock task errors only, authenticated against the disposable local identity server.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://localhost:3022'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({viewport:{width:1366,height:900}}), page = await context.newPage()
const headers = {'X-HX-Request':'1',Origin:base}, output='../../output/playwright/delete-skills', errors=[], writes=[], checks=[]
page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));await mkdir(output,{recursive:true})
const name='故障验收任务 · 保留归档 · 很长的完整任务名称用于窄屏确认', taskId='isolated-ui-fault-task'
let status='studio',version=1,polls=0
const failure='文件清理未完成，已归档成品保留，可重试继续清理'
const task=()=>({id:taskId,workflow:'studio',name,productName:'产品',brand:'HX',platform:'Amazon',market:'美国',remarks:'',skus:[{code:'A'}],version,status,createdAt:'2026-10-13',updatedAt:'2026-10-13',createdBy:{id:'a',name:'管理员'},designer:{id:'d',name:'设计',status:'active',eligible:true},capabilities:['task.read','task.delete'],deletionStatus:['deleting','delete_failed'].includes(status)?status:null,deletionError:status==='delete_failed'?failure:null,events:[]})
const button=(label,scope=page)=>scope.getByRole('button',{name:label,exact:true})
try {
  assert.equal((await context.request.post(`${base}/api/identity/v1/dingtalk/container`,{headers,data:{code:'p18-admin'}})).status(),200)
  const ticket=await context.request.post(`${base}/api/identity/v1/tickets`,{headers,data:{business:'overseas',purpose:'session'}})
  assert.equal((await context.request.post(`${base}/api/overseas/v1/auth/identity/session`,{headers,data:await ticket.json()})).status(),200)
  await context.route(`${base}/api/overseas/v1/tasks**`,async route=>{
    const request=route.request(),path=new URL(request.url()).pathname
    let body
    if(path===`/api/overseas/v1/tasks/${taskId}/deletion`){
      polls++;if(polls===1){await route.abort();return}
      status=writes.length===1?'delete_failed':'deleted';body={taskId,status,error:status==='delete_failed'?failure:null}
    } else if(path===`/api/overseas/v1/tasks/${taskId}`){
      if(request.method()==='DELETE'){const input=request.postDataJSON();assert.deepEqual(input,{version});writes.push(input);version++;status='deleting';body={taskId,status,error:null}}
      else body=task()
    }else if(path==='/api/overseas/v1/tasks')body={items:status==='deleted'?[]:[task()],total:status==='deleted'?0:1,page:1,pageSize:20}
    else{await route.continue();return}
    await route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
  })
  await page.goto(base+'/#/overseas/tasks');const row=page.getByRole('row').filter({hasText:name});await button('删除',row).click()
  const dialog=page.getByRole('dialog',{name:'永久删除任务',exact:true})
  await page.setViewportSize({width:390,height:844});await dialog.getByText('任务：'+name,{exact:true}).waitFor()
  assert.equal(await dialog.getByRole('textbox').count(),0)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))
  await page.screenshot({path:output+'/delete-confirm-mobile.png',fullPage:true,animations:'disabled'})
  await button('确认删除',dialog).click();await dialog.waitFor({state:'hidden'});await button('正在删除',row).waitFor();assert.equal(writes.length,1)
  await page.setViewportSize({width:1366,height:900});await row.getByText('服务连接失败，请稍后重试',{exact:true}).waitFor();assert.equal(await row.count(),1)
  await button('重试删除',row).waitFor();await row.getByText(failure,{exact:true}).waitFor();assert.equal(await row.count(),1)
  await page.screenshot({path:output+'/delete-failure-desktop.png',fullPage:true,animations:'disabled'})
  await button('刷新任务').click();await button('重试删除',row).waitFor();await row.getByText(failure,{exact:true}).waitFor()
  checks.push('模拟轮询断网不移除任务，随后安全失败提示；刷新仍显示删除失败和重试')
  await button('重试删除',row).click();assert.equal(await button('确认删除',dialog).isEnabled(),true)
  assert.equal(await dialog.getByRole('textbox').count(),0);await button('确认删除',dialog).click();await button('正在删除',row).waitFor();assert.equal(writes.length,2)
  await row.waitFor({state:'hidden'});assert.equal(status,'deleted');assert.deepEqual(writes.map(write=>write.version),[1,2])
  checks.push('重试仅二次弹框确认并使用最新版本，后端终态前保留任务，确认deleted后移除')
  assert.deepEqual(errors,[]);await writeFile(output+'/fault-result.json',JSON.stringify({checks,errors,mocked:true},null,2));console.log(JSON.stringify({passed:checks.length,checks,errors},null,2))
} catch(error){console.error(await page.locator('body').innerText());await page.screenshot({path:output+'/fault-failure.png',fullPage:true});throw error}
finally{await context.close();await browser.close()}
