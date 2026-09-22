const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
import { mkdir } from 'node:fs/promises'
const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE ? { executablePath:process.env.BROWSER_EXECUTABLE } : {})})
await mkdir('../../output/create-first-screen-2026-09-22',{recursive:true})
try {
for(const mode of ['wallpaper','product','text']) for(const [width,height] of [[1366,768],[1280,800]]){
 const context=await browser.newContext({viewport:{width,height}});const page=await context.newPage()
 await page.goto(`${process.env.DEMO_URL || 'http://127.0.0.1:3010/'}?role=super_admin#/image-processing/${mode}`);await page.getByRole('textbox',{name:'任务名称',exact:true}).waitFor();await page.waitForLoadState('networkidle')
 for(const state of ['empty','uploaded']){
  if(state==='uploaded'){await page.getByRole('button',{name:'使用示例素材',exact:true}).click();if(mode==='text')await page.getByRole('button',{name:'移除图片 2',exact:true}).click()}
  await page.waitForLoadState('networkidle')
  await page.waitForFunction(()=>[...document.images].filter(i=>i.getBoundingClientRect().width>0).every(i=>i.complete&&i.naturalWidth>0))
  if(state==='empty'){const b=await page.getByText('提交前还需要完成',{exact:true}).boundingBox();if(!b||b.y+b.height>height)throw Error('提交禁用原因不可见')}
  for(const locator of [page.getByRole('textbox',{name:'任务名称',exact:true}),page.getByRole('textbox',{name:'修改要求',exact:true}),page.getByRole('button',{name:'提交生成任务',exact:true})]){
   const b=await locator.boundingBox();if(!b||b.y<0||b.y+b.height>height)throw Error(`${width} ${state} outside viewport: ${JSON.stringify(b)}`)
  }
  await page.screenshot({path:`../../output/create-first-screen-2026-09-22/${mode}-${width}-${state}.png`})
 }
 await page.locator('.hx-demo-tools summary').click();await page.getByRole('combobox',{name:'预览角色'}).waitFor({state:'visible'});await page.locator('.hx-demo-tools summary').click();await page.setViewportSize({width:640,height:800});await page.waitForTimeout(700);const stack=await page.locator('.hx-stack').boundingBox();const form=await page.locator('.hx-summary').boundingBox();if(!stack||!form||form.y<stack.y+stack.height-1)throw Error('窄屏未上下排列');await page.screenshot({path:`../../output/create-first-screen-2026-09-22/${mode}-640.png`});await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('首屏布局验收');await page.getByRole('button',{name:'提交生成任务',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:`../../output/create-first-screen-2026-09-22/${mode}-640-submit.png`});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('窄屏横向溢出');await context.close()
}
console.log('PASS: wallpaper/product/text 1366×768 / 1280×800 empty and uploaded core inputs + submit visible')
}finally{await browser.close()}

