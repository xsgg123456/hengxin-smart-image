async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:3008/?scenario=default#/image-processing/wallpaper');
 await page.reload();
 await page.getByRole('heading',{name:'替换壁纸',exact:true}).waitFor();
 await page.setViewportSize({width:1440,height:1000});
 await page.locator('#app-main').evaluate(e=>{e.scrollTop=0;});
 await page.waitForTimeout(1800);
 await page.screenshot({path:'output/playwright/phase2-wallpaper-1440.png'});
 const widths=[];
 for(const width of [1440,1280]){
   await page.setViewportSize({width,height:1000});
   await page.waitForTimeout(400);
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth||document.querySelector('#app-main').scrollWidth>document.querySelector('#app-main').clientWidth+1)) throw new Error('主页面横向溢出');
   widths.push(width);
 }
 await page.screenshot({path:'output/playwright/phase2-wallpaper-1280.png'});
 await page.getByRole('menuitem',{name:'模板库',exact:true}).click();
 await page.getByRole('button',{name:'新建模板',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'新建套图模板',exact:true});
 await dialog.getByRole('button',{name:'使用示例套图',exact:true}).click();
 await page.waitForTimeout(400);
 await page.screenshot({path:'output/playwright/phase2-editor-1280.png'});
 if(await dialog.evaluate(e=>e.scrollWidth>e.clientWidth+1)) throw new Error('编辑弹窗横向溢出');
 await dialog.getByRole('button',{name:'取消',exact:true}).click();
 if(errors.length)throw new Error(errors.join(';'));
 return 'PASS 1440/1280页面及编辑弹窗无横向溢出，pageerror=0；Art风格截图供视觉核对';
}
