import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})})
const context=await browser.newContext({viewport:{width:1920,height:911}}),page=await context.newPage()
const output='../../output/task-density-2026-09-22';await mkdir(output,{recursive:true});const checks=[]
try{
 await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#/tasks/index`);await page.locator('.task-title').first().waitFor()
 for(let i=0;i<10;i++){await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#/image-processing/text?newTask=${crypto.randomUUID()}`);await page.getByRole('button',{name:'使用示例素材',exact:true}).click();await page.getByRole('textbox',{name:'任务名称',exact:true}).fill(`春季上新 · 商品文案调整 ${i+1}`);await page.getByRole('textbox',{name:'SKU',exact:true}).fill(`SKU-${1000+i}`);await page.getByRole('textbox',{name:'修改要求',exact:true}).fill('更新商品标题');await page.getByRole('button',{name:'提交生成任务',exact:true}).click();await page.locator('.hx-detail').waitFor()}
 await page.goto(`${process.env.DEMO_URL||'http://127.0.0.1:3010/'}?role=super_admin#/tasks/index`)
 await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.el-table__body-wrapper .el-table__row').length===12)
 await page.waitForTimeout(3500)
 for(const [width,height,min] of [[1920,911,8],[1366,768,6],[1280,800,5]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(500);await page.waitForFunction(()=>[...document.images].filter(i=>i.getBoundingClientRect().width>0).every(i=>i.complete&&i.naturalWidth>0))
  const stats=await page.locator('.el-table__body-wrapper .el-table__row').evaluateAll(rows=>({heights:rows.map(e=>e.getBoundingClientRect().height),visible:rows.filter(e=>{const b=e.getBoundingClientRect();return b.y>=0&&b.bottom<=innerHeight}).length,firstTop:rows[0].getBoundingClientRect().y}));assert.ok(stats.visible>=min,`${width}: ${JSON.stringify(stats)}`)
  const row=page.locator('.el-table__body-wrapper .el-table__row').first();for(const label of ['查看详情','删除']){const b=await row.getByRole('button',{name:label,exact:true}).boundingBox();assert.ok(b.x>=0&&b.x+b.width<=width)}
  checks.push({width,height,...stats});await page.screenshot({path:`${output}/tasks-${width}.png`})
 }
 await page.getByText('我的任务',{exact:true}).click();await page.waitForURL(/scope=mine/);await page.reload();assert.ok(await page.getByRole('radio',{name:'我的任务',exact:true}).isChecked());await page.getByText('全员任务',{exact:true}).click()
 await page.getByRole('textbox',{name:'搜索任务',exact:true}).fill('找不到此任务');await page.getByText('暂无匹配任务',{exact:true}).waitFor();await page.getByRole('textbox',{name:'搜索任务',exact:true}).fill('');await page.locator('.task-title').first().waitFor()
 await page.getByRole('button',{name:'删除',exact:true}).first().click();await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.locator('.task-title').count(),12)
 await page.setViewportSize({width:640,height:800});await page.waitForTimeout(700);await page.screenshot({path:`${output}/tasks-640.png`});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 await page.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate(e=>{e.scrollLeft=e.scrollWidth});await page.waitForTimeout(200);const action=page.getByRole('button',{name:'删除',exact:true}).first();const actionBox=await action.boundingBox();assert.ok(actionBox.x>=0&&actionBox.x+actionBox.width<=640);await action.click();await page.getByRole('button',{name:'取消',exact:true}).click();await page.screenshot({path:`${output}/tasks-640-actions.png`});
 await writeFile(`${output}/checks.json`,JSON.stringify(checks,null,2));console.log(JSON.stringify({passed:true,checks}))
}finally{await context.close();await browser.close()}
