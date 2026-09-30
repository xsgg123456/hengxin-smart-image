import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = 'http://127.0.0.1:3024/'
const browser = await chromium.launch({ headless: true })
await mkdir('../../output/playwright/api-only-menu', { recursive: true })
try {
 for (const role of ['designer','operator','design_manager','super_admin']) {
  const context = await browser.newContext(), page = await context.newPage()
  await context.route('**/*', async route => {
   const u = new URL(route.request().url())
   if(u.origin !== new URL(base).origin) return route.abort()
   if(!u.pathname.startsWith('/api/')) return route.continue()
   let body = {}
   if(u.pathname.endsWith('/auth/me')) body = {id:'menu-user',name:'菜单测试',role,status:'active'}
   else if(u.pathname.endsWith('/status')) body = {enabled:true,paused:false,reason:null}
   else if(u.pathname.endsWith('/tasks')) body = {items:[],total:0,page:1,pageSize:20}
   return route.fulfill({contentType:'application/json',body:JSON.stringify(body)})
  })
  await page.goto(base+'#/api-image-edits/records')
  await page.getByRole('heading',{name:'换图记录',exact:true}).waitFor()
  const limited = ['designer','operator'].includes(role)
  const menu = page.locator('.el-menu').first()
  for(const name of ['图片处理','任务中心','模板库','成品库','管理中心']) {
   assert.equal(await menu.getByText(name,{exact:true}).count(),limited?0:1,`${role} ${name}`)
  }
  assert.equal(await menu.getByText('API 换套图',{exact:true}).count(),1)
  if(limited) {
   await page.evaluate(() => {
    const key = Object.keys(localStorage).find(k=>k.includes('worktab'))
    if(!key) throw new Error('Missing persisted worktab')
    const data = JSON.parse(localStorage.getItem(key))
    data.opened.push({path:'/tasks/index',name:'HxtasksPage',title:'任务中心',fixedTab:true})
    data.opened.push({path:'/wallpaper/index',title:'旧替换壁纸',fixedTab:true})
    localStorage.setItem(key,JSON.stringify(data))
    const userKey = Object.keys(localStorage).find(k=>k.endsWith('-user'))
    if(!userKey) throw new Error('Missing persisted user')
    const user = JSON.parse(localStorage.getItem(userKey))
    user.searchHistory = [{path:'/templates/index',name:'HxtemplatesPage',meta:{title:'旧模板入口'}}]
    localStorage.setItem(userKey,JSON.stringify(user))
   })
   await page.reload()
   await page.getByRole('heading',{name:'换图记录',exact:true}).waitFor()
   assert.equal(await page.getByText('任务中心',{exact:true}).count(),0,'旧标签已清理')
   assert.equal(await page.getByText('旧替换壁纸',{exact:true}).count(),0,'旧别名固定标签已清理')
   await page.keyboard.press('Control+k')
   await page.getByRole('dialog').waitFor()
   assert.equal(await page.getByText('旧模板入口',{exact:true}).count(),0,'旧搜索历史已清理')
   await page.keyboard.press('Escape')
   for(const path of ['/image-processing/wallpaper','/tasks/index','/templates/index','/archive/index','/management/usage','/wallpaper/index','/']) {
    await page.goto(base+'#'+path)
    await page.waitForURL('**#/api-image-edits/create')
    await page.getByRole('heading',{name:'新建换图',exact:true}).waitFor()
   }
  }
  await page.waitForTimeout(400)
  await page.screenshot({path:`../../output/playwright/api-only-menu/${role}.png`})
  await context.close()
 }
 console.log('PASS: 四角色菜单、普通角色旧标签清理、隐藏地址/旧别名/首页落地')
} finally { await browser.close() }
