async(page)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:3008/?scenario=default#/image-processing/wallpaper');await page.reload();
 for(const [mode,label] of [['wallpaper','壁纸'],['product','商品'],['text','文字']]){
   await page.goto('http://127.0.0.1:3008/?scenario=default#/image-processing/'+mode);
   await page.getByRole('heading',{name:'替换'+label,exact:true}).waitFor();
   await page.getByRole('button',{name:'使用示例素材'}).click();
   await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('Phase3 '+label+'创建');
   await page.getByRole('textbox',{name:'SKU',exact:true}).fill('SKU-'+mode);
   await page.getByRole('button',{name:'提交生成任务'}).click();
   const drawer=page.getByRole('dialog',{name:'Phase3 '+label+'创建',exact:true});await drawer.waitFor();
   await drawer.getByText('待查看',{exact:true}).waitFor();
   if(await drawer.getByText('v1 · 当前版本',{exact:true}).count()!==(mode==='text'?2:8))throw new Error('输出数不匹配');
   if(mode==='wallpaper'){
     await drawer.getByRole('button',{name:'整套修改'}).click();
     const feedback=page.getByRole('dialog',{name:'整套修改意见',exact:true});await feedback.getByRole('textbox').fill('整套统一光影');await feedback.getByRole('button',{name:'提交修改'}).click();await feedback.waitFor({state:'hidden'});
     await drawer.getByText('v2 · 当前版本',{exact:true}).first().waitFor();
     if(await drawer.getByText('v2 · 当前版本',{exact:true}).count()!==8)throw new Error('整套返工未更新全部');
   }
   await drawer.getByRole('button',{name:'关闭此对话框'}).click();await drawer.waitFor({state:'hidden'});
   await page.getByRole('textbox',{name:'搜索任务',exact:true}).fill('SKU-'+mode);
   await page.getByRole('row').filter({hasText:'Phase3 '+label+'创建'}).waitFor();
 }
 if(errors.length)throw new Error(errors.join(';'));
 return 'PASS 三入口创建、SKU检索、wall/product8张text2张、整套返工8位置全更新，pageerror=0';
}
