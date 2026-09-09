async (page) => {
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  let posts=0, reads=0, failRead=false, delayUpload=true, releaseUpload;
  const gate=new Promise(resolve=>{releaseUpload=resolve;});
  const picture={name:'pixel.png',url:'/samples/wallpaper-0.svg',fileId:'file-1'};
  const skill={id:'skill-wallpaper-1',name:'接口测试 Skill',mode:'wallpaper',version:'1.0.0',checksum:'test-checksum',status:'available',isDefault:true};
  const template={id:'t1',name:'接口测试模板',mode:'wallpaper',images:[picture],skill:skill.name,skillVersionId:skill.id,active:true,version:3,ownerId:'test-user',notes:'',updatedAt:'2026-09-09T00:00:00Z'};
  await page.unroute('**/api/v1/**');
  await page.route('**/api/v1/**', async route=>{
    const url=route.request().url();
    if(url.endsWith('/auth/me')) return route.fulfill({json:{id:'test-user',name:'测试身份',role:'operator',status:'active'}});
    if(url.endsWith('/workspace')) {
      reads++;
      return failRead ? route.fulfill({status:503,json:{code:'UNAVAILABLE',message:'受理后读取失败'}}):route.fulfill({json:{templates:[template],tasks:[],archives:[]}});
    }
    if(url.includes('/templates?')) return route.fulfill({json:{items:[template],page:1,pageSize:4,total:1}});
    if(url.includes('/skills')) return route.fulfill({json:[skill]});
    if(url.endsWith('/files')) {
      if(!route.request().headers()['content-type'].includes('multipart/form-data; boundary=')) throw new Error('不是原生multipart');
      if(!route.request().postData().includes('pixel.png')) throw new Error('未传文件');
      if(delayUpload) await gate;
      return route.fulfill({json:picture});
    }
    if(url.endsWith('/tasks')) {
      posts++; const input=route.request().postDataJSON();
      if(input.templateVersion!==3||input.skillVersionId!==skill.id||input.sources[0].fileId!=='file-1'||input.sku!=='SKU-REAL') throw new Error('提交快照参数错误');
      await page.waitForTimeout(300); failRead=true;
      return route.fulfill({status:202,json:{taskId:'accepted-task',roundId:'r1',state:'排队中'}});
    }
    return route.fulfill({status:404,json:{}});
  });
  await page.goto('http://127.0.0.1:3018/#/image-processing/wallpaper');
  await page.reload();
  await page.getByRole('heading',{name:'替换壁纸',exact:true}).waitFor();
  if(await page.getByRole('button',{name:'使用示例素材'}).count()||await page.getByRole('combobox',{name:'模拟场景'}).count()) throw new Error('真实模式出现模拟入口');
  await page.locator('input[type=file]').setInputFiles('output/playwright/pixel.png');
  await page.getByText('接收中…',{exact:true}).waitFor();
  if(!await page.getByRole('button',{name:'提交生成任务'}).isDisabled()) throw new Error('上传中允许提交');
  await page.getByRole('button',{name:'移除图片 1',exact:true}).click();
  delayUpload=false; releaseUpload();
  await page.waitForTimeout(350);
  if(await page.locator('.picture-meta').count()) throw new Error('迟到上传复活');
  await page.locator('input[type=file]').setInputFiles('output/playwright/pixel.png');
  await page.getByText('已接收',{exact:true}).waitFor();
  await page.getByRole('textbox',{name:'任务名称',exact:true}).fill('真实接口测试');
  await page.getByRole('textbox',{name:'SKU',exact:true}).fill('SKU-REAL');
  await page.getByRole('button',{name:'提交生成任务'}).evaluate(button=>{button.click();button.click();});
  await page.waitForURL('**task=accepted-task');
  await page.getByText('受理后读取失败',{exact:true}).waitFor();
  if(posts!==1) throw new Error('重复创建');
  failRead=false;
  await page.getByRole('button',{name:'重新加载',exact:true}).click();
  await page.getByText('受理后读取失败',{exact:true}).waitFor({state:'hidden'});
  const before=reads; await page.waitForTimeout(1600);
  if(reads<=before) throw new Error('任务页未轮询');
  await page.getByRole('menuitem',{name:'模板库',exact:true}).click();
  const after=reads; await page.waitForTimeout(3400);
  if(reads!==after||posts!==1) throw new Error('离页轮询/读取重试重复写');
  await page.unroute('**/api/v1/**');
  await page.reload();
  await page.getByRole('button',{name:'重新连接',exact:true}).waitFor();
  if(await page.getByRole('menuitem',{name:'模板库',exact:true}).count()) throw new Error('断连回退模拟');
  if(errors.length) throw new Error(errors.join(';'));
  return 'PASS 真实适配multipart与版本参数、上传中阻断/移除迟到不复活、连续双击只POST1次、受理后读取失败不重投、轮询回归、断连无模拟回退，pageerror=0';
}
