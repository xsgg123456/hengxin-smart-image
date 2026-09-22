import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})})
const context=await browser.newContext({viewport:{width:1366,height:768},acceptDownloads:true}),page=await context.newPage()
const output='../../output/archive-library-2026-09-22';await mkdir(output,{recursive:true})
const go=async route=>{await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#${route}`);await page.waitForLoadState('networkidle')}
try{
 await go('/archive/index');const existing=await page.locator('.hx-library-card').count()
 for(let i=existing;i<4;i++){await go(`/image-processing/wallpaper?newTask=${crypto.randomUUID()}`);await page.getByRole('button',{name:'使用示例素材',exact:true}).click();await page.getByRole('textbox',{name:'任务名称',exact:true}).fill(`成品四列验收 ${i}`);await page.getByRole('button',{name:'提交生成任务',exact:true}).click();await page.getByRole('button',{name:'归档到成品库',exact:true}).click()}
 await go('/archive/index');await page.locator('.hx-library-card').nth(3).waitFor()
 for(const [width,height] of [[1920,1080],[1366,768],[1280,800]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(500);await page.waitForFunction(()=>[...document.images].filter(i=>i.getBoundingClientRect().width>0).every(i=>i.complete&&i.naturalWidth>0))
  const cards=page.locator('.hx-library-card');const first=await cards.first().boundingBox()
  for(let i=0;i<4;i++){const card=cards.nth(i),box=await card.boundingBox();assert.ok(Math.abs(box.y-first.y)<2);assert.ok(box.y+box.height<=height,`${width}: card bottom ${box.y+box.height}`);assert.equal(await card.locator('img').first().evaluate(el=>getComputedStyle(el).objectFit),'contain');for(const label of ['查看成品','下载整套示例','删除成品']){const b=await card.getByRole('button',{name:label,exact:true}).boundingBox();assert.ok(b.x>=box.x&&b.x+b.width<=box.x+box.width+1&&b.y+b.height<=box.y+box.height)}}
  await page.screenshot({path:`${output}/archive-${width}.png`})
 }
 await page.locator('.hx-library-card .hx-picture').first().click();await page.keyboard.press('ArrowRight');await page.getByText(/2 \/ \d+/).waitFor();await page.keyboard.press('Escape')
 const card=page.locator('.hx-library-card').first();const download=page.waitForEvent('download');await card.getByRole('button',{name:'下载整套示例',exact:true}).click();assert.ok((await download).suggestedFilename().endsWith('.zip'))
 await card.getByRole('button',{name:'查看成品',exact:true}).click();await page.getByText('归档图片 · 后续修改不会覆盖此版本',{exact:true}).waitFor();await page.keyboard.press('Escape')
 await card.getByRole('button',{name:'删除成品',exact:true}).click();await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.locator('.hx-library-card').count(),4)
 await page.getByRole('textbox',{name:'搜索成品名称'}).fill('没有这套成品');await page.getByText('暂无匹配成品，可清除筛选或归档任务结果').waitFor();await page.getByRole('button',{name:'清除筛选',exact:true}).click();await page.locator('.hx-library-card').nth(3).waitFor()
 await page.setViewportSize({width:640,height:800});await page.waitForTimeout(700);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:`${output}/archive-640.png`})
 console.log('PASS: four archived tasks in isolated Demo; 1920/1366/1280 complete first row/actions; preview arrows, ZIP download, details, delete cancel, search clear and 640')
}finally{await context.close();await browser.close()}
