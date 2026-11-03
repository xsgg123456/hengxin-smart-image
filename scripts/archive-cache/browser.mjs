// No request routing: Chromium must retain its real private HTTP cache.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile, rm } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { startFixture, imageBytes } from './fixture-server.mjs'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const output = resolve('output/archive-cache'); await mkdir(output,{recursive:true})
const fixture = await startFixture(), { state, origin } = fixture
const browser = await chromium.launch({headless:true}), context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true}), page = await context.newPage()
const checks=[], errors=[], evidence={}; page.on('pageerror',e=>errors.push(e.message)); page.setDefaultTimeout(20000)
const originals = () => state.requests.filter(r=>!r.small && r.method==='GET')
const viewer = () => page.locator('.el-image-viewer__wrapper')
const dialog = () => page.getByRole('dialog',{name:'归档成品',exact:true})
const settle = () => page.waitForFunction(()=>{const s=window.archiveTest.cache.stats();return !s.active&&!s.queued})
const visible = () => page.waitForFunction(()=>[...document.querySelectorAll('.el-image-viewer__img')].some(img=>getComputedStyle(img).display!=='none'&&img.naturalWidth===1600&&img.naturalHeight===1000))
const shot = name => page.screenshot({path:resolve(output,name+'.png'),animations:'disabled'})
const openDetail = async () => { await page.getByRole('button',{name:'查看成品',exact:true}).click(); await dialog().waitFor();await dialog().locator('.archive-pictures > div').first().waitFor() }
const closeDetail = async () => { await dialog().getByRole('button',{name:'关闭',exact:true}).click(); await dialog().waitFor({state:'hidden'}) }
const closeViewer = async () => { await page.keyboard.press('Escape'); await viewer().waitFor({state:'hidden'}) }
const reset = async () => { state.status.clear();state.metadataStatus=200;state.delays.clear();state.thumbnailDelay=0; await page.evaluate(()=>window.archiveTest.reset()); await page.getByRole('button',{name:'查看成品',exact:true}).waitFor() }
try {
  state.thumbnailFailures.set('a',1);await page.goto(origin);await page.getByRole('button',{name:'重试封面',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.archive-cover img')?.naturalWidth===240)
  assert.equal(originals().length,0); checks.push('正式列表封面仅thumbnail=true，首次失败手动重试恢复240×150完整缩略图，列表零原件GET'); await shot('01-list')
  const coldStart=performance.now(); await openDetail(); await settle()
  await page.waitForFunction(()=>[...document.querySelectorAll('.archive-picture img')].length===6&&[...document.querySelectorAll('.archive-picture img')].every(img=>img.naturalWidth===240))
  assert.equal(originals().length,6);assert.ok(state.maxActive<=2)
  evidence.cold={elapsedMs:Math.round(performance.now()-coldStart),originalGets:6,bodyBytes:originals().reduce((n,r)=>n+r.bytes,0)}
  checks.push('正式详情6张小图全部缩略图，当前套图6张原件渐进预取且最大并发2，来源任务删除仍可读'); await shot('02-detail')
  const gets=originals().length, hotStart=performance.now()
  await dialog().getByRole('button',{name:'预览 a.png',exact:true}).click(); await visible(); await settle()
  await page.keyboard.press('ArrowRight');await visible();await settle();await page.keyboard.press('ArrowLeft');await visible();await settle()
  const image=page.locator('.el-image-viewer__img:visible'), before=await image.evaluate(img=>img.style.transform)
  await image.hover();await page.mouse.wheel(0,-180)
  await page.waitForFunction(before=>[...document.querySelectorAll('.el-image-viewer__img')].some(img=>getComputedStyle(img).display!=='none'&&img.style.transform!==before),before)
  await closeViewer();await dialog().getByRole('button',{name:'预览 a.png',exact:true}).click();await visible();await settle()
  assert.equal(originals().length,gets);assert(state.requests.some(r=>r.method==='HEAD'&&r.status===304))
  evidence.hot={elapsedMs:Math.round(performance.now()-hotStart),additionalOriginalGets:originals().length-gets,additionalBodyBytes:0}
  checks.push('放大/左右切回/关闭重开复用缓存，只HEAD304，无原件正文重传；滚轮缩放仍为1600×1000');await shot('03-viewer')
  const downloading=page.waitForEvent('download');await viewer().getByRole('button',{name:'下载原图',exact:true}).click();const file=await downloading
  await file.saveAs(resolve(output,'download-original.png'));const hash=b=>createHash('sha256').update(b).digest('hex')
  evidence.download={actual:hash(await readFile(resolve(output,'download-original.png'))),expected:hash(imageBytes('a'))};assert.equal(evidence.download.actual,evidence.download.expected)
  await closeViewer();await closeDetail();checks.push('查看器下载SHA256与1600×1000原件一致')
  const refreshAt=state.requests.length;await page.reload();await page.waitForFunction(()=>!!window.archiveTest);await openDetail();await settle()
  const reloaded=state.requests.slice(refreshAt).filter(r=>!r.small&&r.method==='GET');assert.equal(reloaded.length,6);assert(reloaded.every(r=>r.status===304&&r.bytes===0))
  checks.push('真实Chromium刷新后6张原图GET均为304，零正文，权限校验仍经过服务端');await closeDetail()

  await reset();state.thumbnailDelay=3500;for(const id of ['a','b','c','d','e','f'])state.delays.set(id,250)
  await openDetail();const downloadButton=dialog().getByRole('button',{name:'下载图片',exact:true}).first();assert(await downloadButton.isEnabled())
  const pending=page.waitForEvent('download');await downloadButton.click();await pending
  assert.equal(await dialog().getByRole('button',{name:'预览 a.png',exact:true}).count(),0);checks.push('缩略图仍在加载时下载按钮可用，下载点击独立取得原件');await closeDetail()

  await reset();for(const id of ['a','b','c','d','e','f'])state.delays.set(id,1800)
  const cancelAt=state.requests.length;await openDetail();await page.waitForFunction(()=>window.archiveTest.cache.stats().active===2)
  await dialog().locator('.el-select__wrapper').click();await page.getByRole('option',{name:'会话二',exact:true}).click()
  await page.waitForFunction(()=>document.querySelectorAll('.archive-picture').length===3)
  await closeDetail();await settle()
  const cancelled=state.requests.slice(cancelAt);assert(cancelled.some(r=>!r.small&&r.aborted));assert(!cancelled.some(r=>r.id==='c'&&!r.small&&r.method==='GET'))
  checks.push('详情会话筛选取消旧套图队列，关闭详情中止无用在途，不启动旧组第三张');evidence.cancelled=cancelled
  await reset();for(const id of ['a','b','c','d','e','f'])state.delays.set(id,1800)
  await page.getByRole('button',{name:'预览 真实组件测试成品',exact:true}).click();await page.waitForFunction(()=>window.archiveTest.cache.stats().active===2)
  await page.getByRole('textbox',{name:'搜索成品',exact:true}).fill('无结果');await viewer().waitFor({state:'hidden'});await settle()
  checks.push('成品列表筛选关闭直接查看器并取消整套原件预取')

  await reset();state.status.set('a',500);await page.getByRole('button',{name:'预览 真实组件测试成品',exact:true}).click()
  await viewer().getByRole('button',{name:'重新加载图片',exact:true}).waitFor();state.status.delete('a')
  await viewer().getByRole('button',{name:'重新加载图片',exact:true}).click();await visible();await settle();checks.push('真实原图500错误提示后可重试恢复');await closeViewer()
  state.status.set('a',403);await page.getByRole('button',{name:'预览 真实组件测试成品',exact:true}).click();await viewer().waitFor({state:'hidden'});await settle()
  assert.equal(await page.evaluate(()=>window.archiveTest.cache.stats().entries),0);assert.equal(await page.locator('.el-image-viewer__img[src^="blob:"]').count(),0)
  checks.push('缓存原图重新打开仍校验权限，403清整套缓存并隐藏图片');await shot('04-permission')
  await reset();await openDetail();await settle();await closeDetail();await page.evaluate(()=>window.archiveTest.api.remove('fixture','fixture-token'));assert.equal(await page.evaluate(()=>window.archiveTest.cache.stats().entries),0)
  checks.push('归档删除响应即清理整套原件缓存')
  await reset();await openDetail();await settle();await page.evaluate(()=>window.archiveTest.switchAccount());await settle();assert.equal(await page.evaluate(()=>window.archiveTest.cache.stats().entries),0)
  checks.push('换号清空缓存并取消旧视图读取')
  await page.setViewportSize({width:390,height:844});await openDetail();await settle();await page.waitForFunction(()=>[...document.querySelectorAll('.archive-picture img')].every(img=>img.naturalWidth===240));await shot('05-narrow-detail')
  const bounds=await dialog().evaluate(el=>{const r=el.getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}})
  assert(bounds.left>=0&&bounds.right<=bounds.width+1&&bounds.scroll<=bounds.client+1)
  const narrowDownload=dialog().getByRole('button',{name:'下载图片',exact:true}).first();await narrowDownload.scrollIntoViewIfNeeded();assert(await narrowDownload.isVisible());await shot('06-narrow-download');await closeDetail();await page.getByRole('button',{name:'退出账号',exact:true}).click()
  assert.equal(await page.evaluate(()=>window.archiveTest.cache.stats().entries),0);assert.equal(await page.locator('.archive-cover').count(),0)
  checks.push('390px窄屏详情无横向裁切且下载可达；退出清缓存及图片')
  assert.deepEqual(state.unexpected,[]);assert.deepEqual(errors,[])
  await writeFile(resolve(output,'result.json'),JSON.stringify({passed:true,scope:'隔离localhost真实HTTP+正式Vue组件，不代表生产耗时或真实后端权限验收',checks,evidence,requests:state.requests,errors},null,2))
  await rm(resolve(output,'failure.json'),{force:true});await rm(resolve(output,'failure.png'),{force:true})
  console.log(JSON.stringify({passed:true,checks,evidence,output},null,2))
} catch(error) {await shot('failure').catch(()=>{});await writeFile(resolve(output,'failure.json'),JSON.stringify({error:String(error),stack:error.stack,checks,errors,requests:state.requests},null,2));throw error}
finally {await context.close();await browser.close();await fixture.close()}
