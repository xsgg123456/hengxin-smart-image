async(page)=>{
 await page.goto('http://127.0.0.1:3008/?scenario=default#/tasks/index');await page.reload();
 await page.getByRole('heading',{name:'任务中心',exact:true}).waitFor();
 for(const width of [1440,1280]){
   await page.setViewportSize({width,height:1000});await page.locator('#app-main').evaluate(e=>{e.scrollTop=0;});await page.waitForTimeout(1400);
   if(await page.evaluate(()=>document.querySelector('#app-main').scrollWidth>document.querySelector('#app-main').clientWidth+1))throw new Error('主内容横溢出');
   await page.screenshot({path:'output/playwright/phase3-tasks-'+width+'.png'});
 }
 await page.getByRole('button',{name:'查看详情'}).first().click();const drawer=page.getByRole('dialog');await drawer.waitFor();await page.waitForTimeout(500);
 await page.screenshot({path:'output/playwright/phase3-detail-1280.png'});
 if(await drawer.evaluate(e=>e.scrollWidth>e.clientWidth+1))throw new Error('详情横溢出');
 await drawer.getByRole('button',{name:'关闭此对话框'}).click();await drawer.waitFor({state:'hidden'});
 await page.getByRole('menuitem',{name:'成品库',exact:true}).click();await page.getByRole('heading',{name:'成品库',exact:true}).waitFor();await page.waitForTimeout(1400);
 await page.screenshot({path:'output/playwright/phase3-archive-1280.png'});
 await page.getByRole('menuitem',{name:'模板库',exact:true}).click();await page.getByRole('heading',{name:'模板库',exact:true}).waitFor();await page.waitForTimeout(1400);
 await page.screenshot({path:'output/playwright/phase3-neighbor-template.png'});
 return 'PASS 1440/1280任务页及1280抽屉无横向溢出；任务/详情/成品/相邻模板截图已生成';
}
