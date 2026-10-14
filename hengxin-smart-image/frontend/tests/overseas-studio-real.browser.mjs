// Only infra/identity-test/run.py --requirements --serve disposable topology. No model worker.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3017'
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname))
const headers = { 'X-HX-Request':'1',Origin:base }, browser = await chromium.launch({headless:true})
const context = await browser.newContext({viewport:{width:1366,height:900}})
async function call(method,path,data,key) {
  const response=await context.request[method](`${base}/api/overseas/v1${path}`,{headers:{...headers,...(key?{'Idempotency-Key':key}:{})},data})
  assert.ok(response.ok(),`${method} ${path}: ${response.status()} ${await response.text()}`);return response.json()
}
try {
  const auth=await context.request.post(`${base}/api/identity/v1/dingtalk/container`,{headers,data:{code:'p18-admin'}});assert.equal(auth.status(),200)
  const ticketResponse=await context.request.post(`${base}/api/identity/v1/tickets`,{headers,data:{business:'overseas',purpose:'session'}});assert.equal(ticketResponse.status(),200)
  await call('post','/auth/identity/session',await ticketResponse.json())
  await call('get','/auth/me')
  const designers=await call('get','/task-designers?page=1&pageSize=20');assert.ok(designers.items.length)
  const upload=await context.request.post(`${base}/api/overseas/v1/materials?kind=competitor`,{headers,multipart:{file:{name:'任务素材.csv',mimeType:'text/csv',buffer:Buffer.from('product,feature\nlamp,warm light')}}});assert.ok(upload.ok(),await upload.text());const material=await upload.json()
  let task=await call('post','/tasks',{name:`工作台验收-${Date.now()}`,productName:'灯具',brand:'HX',platform:'Amazon',market:'美国',remarks:'真实隔离接口验证',skus:[{code:'SKU-A'},{code:'SKU-B'}],designerId:designers.items[0].id,materialIds:[material.id]},crypto.randomUUID())
  assert.equal(task.workflow,'studio');assert.equal(task.status,'pending_review')
  task=await call('post',`/tasks/${task.id}/requirements-review`,{decision:'approve',comment:'资料完整',version:task.version},crypto.randomUUID());assert.equal(task.status,'studio')
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
  await page.goto(`${base}/#/overseas/tasks/${task.id}`);await page.getByText('与 Codex 协作',{exact:true}).waitFor()
  assert.equal(await page.getByRole('menuitem',{name:'海外业务',exact:true}).count(),0)
  async function downloadOriginal(id, name, expected) {
    const event = page.waitForEvent('download')
    await page.locator(`.studio-source-file[data-material-id="${id}"]`).getByRole('button', { name: '下载原文件', exact: true }).click()
    const file = await event, chunks = []; assert.equal(file.suggestedFilename(), name)
    for await (const chunk of await file.createReadStream()) chunks.push(chunk)
    assert.equal(Buffer.concat(chunks).toString(), expected)
  }
  await downloadOriginal('task:' + material.id, '任务素材.csv', 'product,feature\nlamp,warm light')
  await page.locator('.studio-materials label').filter({ hasText: '全选素材' }).click(); assert.equal(await page.getByRole('checkbox',{name:'全选素材',exact:true}).isChecked(),true);await page.getByRole('button',{name:/引用所选素材/}).click()
  assert.equal(await page.getByRole('button',{name:'移除 任务素材.csv',exact:true}).count(),1)
  await page.getByRole('button',{name:'移除 任务素材.csv',exact:true}).click();assert.equal(await page.getByRole('checkbox',{name:'任务素材.csv',exact:true}).count(),1)
  await page.locator('input[type=file]').setInputFiles({name:'补充.txt',mimeType:'text/plain',buffer:Buffer.from('Please use warm lighting.')})
  await page.getByRole('button',{name:'移除 补充.txt',exact:true}).waitFor()
  const uploadedState = await call('get',`/tasks/${task.id}/studio`)
  await downloadOriginal(uploadedState.materials.find(a => a.source === 'upload').id, '补充.txt', 'Please use warm lighting.')
  await page.getByRole('textbox',{name:'设计要求',exact:true}).fill('请先阅读资料，用文字说明设计方向。')
  await page.getByRole('button',{name:'刷新任务详情',exact:true}).click();assert.equal(await page.getByRole('textbox',{name:'设计要求',exact:true}).inputValue(),'请先阅读资料，用文字说明设计方向。')
  await page.getByRole('button',{name:'展开工作台',exact:true}).click();assert.equal(await page.getByRole('textbox',{name:'设计要求',exact:true}).inputValue(),'请先阅读资料，用文字说明设计方向。')
  await page.getByRole('button',{name:'发送',exact:true}).click();await page.getByRole('button',{name:'停止',exact:true}).waitFor()
  await page.reload();await page.getByRole('button',{name:'停止',exact:true}).waitFor();assert.equal(await page.getByText('请先阅读资料，用文字说明设计方向。',{exact:true}).count(),1)
  const state=await call('get',`/tasks/${task.id}/studio`);assert.equal(state.turns.length,1);assert.ok(state.activeTurnId)
  await page.getByRole('button',{name:'停止',exact:true}).click();await page.getByRole('button',{name:'发送',exact:true}).waitFor()
  await mkdir('../../output/playwright/studio',{recursive:true});await page.screenshot({path:'../../output/playwright/studio/studio-real.png',fullPage:true})
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'展开工作台',exact:true}).click();await page.getByRole('button',{name:'收起',exact:true}).click()
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))
  await page.screenshot({path:'../../output/playwright/studio/studio-real-mobile.png',fullPage:true})
  assert.deepEqual(errors,[]);console.log(`PASS studio real HTTP flow; task=${task.id}; no model invoked`)
} finally {await context.close();await browser.close()}
