import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium }=await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})})
const output='../../output/template-layout-2026-09-22';await mkdir(output,{recursive:true})
const context=await browser.newContext({viewport:{width:1366,height:768}}),page=await context.newPage()
const go=async route=>{await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#${route}`);await page.waitForLoadState('networkidle')}
const ready=async()=>{await page.waitForTimeout(400);await page.waitForFunction(()=>[...document.images].filter(i=>i.getBoundingClientRect().width>0).every(i=>i.complete&&i.naturalWidth>0))}
try {
 await go('/templates/index');await page.getByRole('button',{name:'新建模板',exact:true}).click();await page.getByPlaceholder('给这套模板起个容易找到的名字').fill('三列布局验收模板');await page.getByRole('button',{name:'使用示例套图',exact:true}).click();await page.getByRole('button',{name:'保存模板',exact:true}).click();await page.getByRole('heading',{name:'三列布局验收模板',exact:true}).waitFor()
 await go('/image-processing/wallpaper');await page.getByRole('button',{name:'更换模板',exact:true}).waitFor();await ready()
 await page.getByRole('button',{name:'更换模板',exact:true}).click();await page.locator('.hx-template-option').filter({hasText:'极简光影'}).getByRole('button',{name:'使用此模板'}).click();await ready();assert.equal(await page.locator('.hx-template-filmstrip .hx-picture').count(),6)
 await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('保留我的任务名称')
 await ready();const original=await page.locator('.hx-selected-template strong').innerText();const uploadBefore=await page.locator('.image-upload').boundingBox()
 await page.screenshot({path:`${output}/default-1366.png`})
 await page.getByRole('button',{name:'更换模板',exact:true}).click();await ready();const cards=page.locator('.hx-template-option');assert.equal(await cards.count(),3)
 const positions=await cards.evaluateAll(els=>els.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));assert.ok(positions.every(p=>Math.abs(p.y-positions[0].y)<2));assert.ok(positions[2].x>positions[1].x)
 await page.screenshot({path:`${output}/picker-1366.png`})
 await cards.filter({hasText:'极简光影'}).locator('.hx-picture').first().click();await page.keyboard.press('ArrowRight');await page.getByText('2 / 8',{exact:false}).waitFor();await page.keyboard.press('Escape');await page.getByRole('button',{name:'取消更换',exact:true}).click();await page.getByRole('dialog',{name:'选择套图模板',exact:true}).waitFor({state:'hidden'});await ready()
 assert.equal(await page.locator('.hx-selected-template strong').innerText(),original);assert.equal(await page.getByRole('textbox',{name:'任务名称',exact:true}).inputValue(),'保留我的任务名称');assert.equal((await page.locator('.image-upload').boundingBox()).height,uploadBefore.height)
 await page.getByRole('button',{name:'更换模板',exact:true}).click();await page.getByRole('textbox',{name:'搜索可用模板'}).fill('不存在的名字');await page.getByText('暂无匹配模板，请调整搜索或到模板库创建').waitFor();await page.getByRole('textbox',{name:'搜索可用模板'}).fill('');await cards.nth(2).waitFor();const other=cards.filter({hasText:'三列布局验收模板'});const next=await other.locator('strong').innerText();await other.getByRole('button',{name:'使用此模板'}).click();await ready();assert.equal(await page.locator('.hx-selected-template strong').innerText(),next)
 await page.setViewportSize({width:1920,height:1080});await page.waitForTimeout(500);await page.screenshot({path:`${output}/default-1920.png`})
 await page.setViewportSize({width:640,height:800});await page.waitForTimeout(700);await page.getByRole('button',{name:'更换模板',exact:true}).click();await ready();await page.screenshot({path:`${output}/picker-640.png`});assert.ok(await page.getByRole('button',{name:'取消更换',exact:true}).isVisible());assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 console.log('PASS: 6-image default, 3-column picker with 3 real test templates, preview/escape/cancel/search/select preserve inputs and upload layout, 1920/1366/640')
}finally{await context.close();await browser.close()}
