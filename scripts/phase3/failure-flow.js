async(page)=>{
 const downloads=[];page.on('download',d=>downloads.push(d));
 for(const scenario of ['partial-result','execution-error']){
   await page.goto('http://127.0.0.1:3008/?scenario='+scenario+'#/image-processing/wallpaper');
   await page.reload();
   await page.getByRole('button',{name:'使用示例素材'}).click();
   await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('Phase3 '+scenario);
   await page.getByRole('button',{name:'提交生成任务'}).click();
   const drawer=page.getByRole('dialog',{name:'Phase3 '+scenario,exact:true});await drawer.waitFor();
   if(await drawer.locator('.hx-result-grid .el-image').count())throw new Error('受理时提前填输出');
   await drawer.getByRole('button',{name:'重试失败范围'}).waitFor();
   const count=scenario==='partial-result'?7:0;
   if(await drawer.locator('.hx-result-grid .el-image').count()!==count)throw new Error('失败结果数量不符');
   if(!await drawer.getByRole('button',{name:'归档到成品库'}).isDisabled())throw new Error('残缺套图允许归档');
   if(scenario==='partial-result'){
     const event=page.waitForEvent('download');await drawer.getByRole('button',{name:'下载示例',exact:true}).first().click();await event;
     await page.screenshot({path:'output/playwright/phase3-partial.png'});
   }
   await drawer.getByRole('button',{name:'重试失败范围'}).click();
   await drawer.getByRole('button',{name:'归档到成品库'}).click();
   await drawer.getByRole('button',{name:'再次归档当前整套'}).waitFor();
   if(await drawer.locator('.hx-result-grid .el-image').count()!==8)throw new Error('重试未恢复完整输出');
 }
 await page.goto('http://127.0.0.1:3008/?scenario=archive-error#/tasks/index?task=HX0908-001');
 const drawer=page.getByRole('dialog',{name:'秋日山川 · 手机屏幕系列',exact:true});await drawer.waitFor();
 await drawer.getByRole('button',{name:'归档到成品库'}).click();
 await drawer.getByText('模拟归档失败，请重试；当前结果保留',{exact:true}).waitFor();
 await drawer.getByRole('button',{name:'归档到成品库'}).click();
 await drawer.getByRole('button',{name:'再次归档当前整套'}).waitFor();
 const initial=downloads.length;
 await page.route('**/samples/wallpaper-0.svg',route=>route.fulfill({status:200,contentType:'text/html',body:'<html>错误网关</html>'}));
 await drawer.getByRole('button',{name:'下载示例',exact:true}).first().click();
 await page.getByText('下载失败：图片不可用或请求超时，请重试',{exact:true}).waitFor();
 if(downloads.length!==initial)throw new Error('HTML错误下载成图片');
 await page.unroute('**/samples/wallpaper-0.svg');
 await page.route('**/samples/wallpaper-1.svg',route=>route.fulfill({status:503,body:'offline'}));
 await drawer.getByRole('button',{name:'下载整套示例'}).click();
 await page.getByText('打包失败：请检查图片并重试，未下载残缺套图',{exact:true}).waitFor();
 if(downloads.length!==initial)throw new Error('打包失败下载了残缺包');
 await page.unroute('**/samples/wallpaper-1.svg');
 const event=page.waitForEvent('download');await drawer.getByRole('button',{name:'下载整套示例'}).click();await event;
 if(downloads.length!==initial+1)throw new Error('下载重试次数异常');
 return 'PASS 首次生成不提前填图、部分成功7/8单图可下载不可归档、全失败0/8、失败重试恢复、归档失败重试、HTML拒绝与残缺ZIP不保存、下载重试1次';
}
