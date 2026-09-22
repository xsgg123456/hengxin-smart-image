import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})})
const context=await browser.newContext({viewport:{width:1366,height:768}}),page=await context.newPage()
const output='../../output/template-library-2026-09-22';await mkdir(output,{recursive:true})
try{
 await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#/templates/index`);await page.waitForLoadState('networkidle')
 while(await page.locator('.hx-library-card').count()<4){await page.getByRole('button',{name:'新建模板',exact:true}).click();await page.getByPlaceholder('给这套模板起个容易找到的名字').fill('四列验收模板');await page.getByRole('button',{name:'使用示例套图',exact:true}).click();await page.getByRole('button',{name:'保存模板',exact:true}).click();await page.getByRole('heading',{name:'四列验收模板',exact:true}).waitFor()}
 for(const [width,height] of [[1920,1080],[1366,768],[1280,800]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(500);await page.waitForFunction(()=>[...document.images].filter(i=>i.getBoundingClientRect().width>0).every(i=>i.complete&&i.naturalWidth>0))
  const cards=page.locator('.hx-library-card');const first=await cards.first().boundingBox()
  for(let i=0;i<4;i++){const card=cards.nth(i),box=await card.boundingBox();assert.ok(Math.abs(box.y-first.y)<2);assert.ok(box.y+box.height<=height,`${width}: card bottom ${box.y+box.height}`);assert.equal(await card.locator('img').first().evaluate(el=>getComputedStyle(el).objectFit),'contain');for(const label of ['使用模板','配置模板','历史版本','删除模板']){const b=await card.getByRole('button',{name:label,exact:true}).boundingBox();assert.ok(b.x>=box.x&&b.x+b.width<=box.x+box.width+1&&b.y+b.height<=box.y+box.height)}}
  await page.screenshot({path:`${output}/library-${width}.png`})
 }
 await page.locator('.hx-library-card .hx-picture').first().click();await page.keyboard.press('ArrowRight');await page.getByText(/2 \/ \d+/).waitFor();await page.keyboard.press('Escape')
 await page.getByRole('textbox',{name:'搜索模板名称'}).fill('没有此模板');await page.getByText('暂无匹配模板，可新建或清除筛选').waitFor();await page.getByRole('textbox',{name:'搜索模板名称'}).fill('');await page.locator('.hx-library-card').first().waitFor()
 await page.setViewportSize({width:640,height:800});await page.waitForTimeout(700);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:`${output}/library-640.png`})
 console.log('PASS: 1920/1366/1280 four cards same row fully within viewport, all actions inside cards, contain previews and arrows, search empty state, 640 no overflow')
}finally{await context.close();await browser.close()}

