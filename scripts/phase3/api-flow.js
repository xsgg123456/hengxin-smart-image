async(page)=>{
 let listReads=0, detailReads=0, revisionPosts=0, archivePosts=0;
 let taskReadFailure=false, taskListFailure=false, archiveListFailure=false, detailFailure=false, deleteFailure=true, archiveDeleteFailure=true;
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const picture={name:'API图片',url:'/samples/wallpaper-0.svg',version:1,fileId:'f1'};
 let tasks=Array.from({length:25},(_,i)=>({id:'api-task-'+i,name:'API任务 '+String(i).padStart(2,'0'),mode:'wallpaper',template:'模板',skillVersionId:'s1',ownerId:'u1',sessionId:null,state:'待查看',progress:null,images:[picture],sources:[],feedback:[],time:'2026-09-09T02:00:00Z',archived:false,currentRoundId:'r1',outputCount:1}));
 let archives=Array.from({length:13},(_,i)=>({id:'a'+i,name:'API成品 '+String(i).padStart(2,'0'),mode:'wallpaper',images:[picture],time:'2026-09-09T02:00:00Z',ownerId:'u1',imageVersionIds:['v1']}));
 const query=(url,key)=>decodeURIComponent((url.match(new RegExp('[?&]'+key+'=([^&]*)'))||[])[1]?.replace(/\+/g,' ')||'');
 const pageBody=(items,url)=>{const current=Number(query(url,'page')||1),size=Number(query(url,'pageSize')||12);return {items:items.slice((current-1)*size,current*size),page:current,pageSize:size,total:items.length};};
 await page.unroute('**/api/v1/**');
 await page.route('**/api/v1/**',async route=>{
   const url=route.request().url(),method=route.request().method();
   if(url.endsWith('/auth/me'))return route.fulfill({json:{id:'u1',name:'接口验收',role:'operator',status:'active'}});
   if(url.endsWith('/workspace'))return route.fulfill({json:{templates:[],tasks:[],archives:[]}});
   if(url.includes('/tasks?')){
     listReads++;if(taskListFailure)return route.fulfill({status:503,json:{message:'任务列表失败'}});
     const search=query(url,'search'),items=tasks.filter(t=>t.name.includes(search));
     if(search==='API任务 00')await page.waitForTimeout(500);
     return route.fulfill({json:{...pageBody(items,url),stats:{total:tasks.length,processing:0,ready:tasks.length,archived:archives.length}}});
   }
   if(url.includes('/archives?')){
     if(archiveListFailure)return route.fulfill({status:503,json:{message:'成品列表暂时失败'}});
     const search=query(url,'search');return route.fulfill({json:pageBody(archives.filter(a=>a.name.includes(search)),url)});
   }
   if(url.match(/\/tasks\/[^/]+\/rounds$/)){
     revisionPosts++;const input=route.request().postDataJSON();if(input.note!=='API返工保留意见')throw new Error('意见丢失');
     if(revisionPosts===1)return route.fulfill({status:503,json:{message:'返工提交失败'}});
     taskReadFailure=true;return route.fulfill({status:202,json:{taskId:'api-task-1',roundId:'r2',state:'排队中'}});
   }
   if(url.match(/\/tasks\/[^/]+\/archives$/)){
     archivePosts++;taskReadFailure=true;
     return route.fulfill({json:archives[0]});
   }
   if(url.includes('/tasks/')){
     const id=url.split('/tasks/')[1],task=tasks.find(t=>t.id===id);
     if(method==='DELETE'){
       if(deleteFailure){deleteFailure=false;return route.fulfill({status:503,json:{message:'任务删除失败'}});}
       tasks=tasks.filter(t=>t.id!==id);return route.fulfill({json:{id,operatorId:'u1',deletedAt:'2026-09-09'}});
     }
     detailReads++;if(taskReadFailure||detailFailure){detailFailure=false;return route.fulfill({status:503,json:{message:'任务详情暂时失败'}});}
     if(!task)return route.fulfill({status:404,json:{code:'NOT_FOUND',message:'任务已删除'}});
     return route.fulfill({json:{task,slots:[{slot:0,currentVersionId:'v1',error:null,versions:[{...picture,id:'v1',roundId:'r1',createdAt:task.time}]}],rounds:[{id:'r1',taskId:id,operatorId:'u1',target:null,note:'初始生成',state:'待查看',createdAt:task.time,startedAt:task.time,finishedAt:task.time,error:null}]}});
   }
   if(url.includes('/archives/')){
     const id=url.split('/archives/')[1];
     if(method==='DELETE'){
       if(archiveDeleteFailure){archiveDeleteFailure=false;return route.fulfill({status:503,json:{message:'成品删除失败'}});}
       archives=archives.filter(a=>a.id!==id);return route.fulfill({status:204});
     }
     if(id==='a0')await page.waitForTimeout(500);
     return route.fulfill({json:archives.find(a=>a.id===id)});
   }
   return route.fulfill({status:404,json:{}});
 });
 await page.goto('http://127.0.0.1:3018/#/tasks/index');await page.reload();
 await page.getByRole('row').filter({hasText:'API任务 00'}).waitFor();
 if(await page.locator('.el-table__body tbody tr').count()!==12)throw new Error('任务第一页不为12');
 if(await page.getByRole('progressbar').count())throw new Error('null进度伪造百分比');
 await page.getByRole('button',{name:'下一页',exact:true}).click();
 await page.getByRole('row').filter({hasText:'API任务 12'}).waitFor();
 await page.getByRole('textbox',{name:'搜索任务',exact:true}).fill('API任务 00');await page.waitForTimeout(100);
 await page.getByRole('textbox',{name:'搜索任务',exact:true}).fill('API任务 01');
 await page.getByRole('row').filter({hasText:'API任务 01'}).waitFor();await page.waitForTimeout(600);
 if(await page.getByRole('row').filter({hasText:'API任务 00'}).count())throw new Error('旧列表响应覆盖新搜索');
 detailFailure=true;await page.getByRole('button',{name:'查看详情'}).click();
 let drawer=page.getByRole('dialog',{name:'任务详情',exact:true});
 await drawer.getByText('任务详情暂时失败',{exact:true}).waitFor();await drawer.getByRole('button',{name:'重试加载'}).click();
 drawer=page.getByRole('dialog',{name:'API任务 01',exact:true});await drawer.waitFor();
 await drawer.getByRole('button',{name:'整套修改'}).click();
 const feedback=page.getByRole('dialog',{name:'整套修改意见',exact:true});await feedback.getByRole('textbox').fill('API返工保留意见');
 await feedback.getByRole('button',{name:'提交修改'}).click();await feedback.getByText('返工提交失败',{exact:true}).waitFor();
 if(await feedback.getByRole('textbox').inputValue()!=='API返工保留意见')throw new Error('提交失败丢意见');
 await feedback.getByRole('button',{name:'提交修改'}).evaluate(button=>{button.click();button.click();});await feedback.waitFor({state:'hidden'});
 await drawer.getByText('任务详情暂时失败',{exact:true}).waitFor();if(revisionPosts!==2)throw new Error('返工重复写');
 taskReadFailure=false;await drawer.getByRole('button',{name:'重试加载'}).click();
 await drawer.getByRole('button',{name:'归档到成品库'}).click();await drawer.getByText('任务详情暂时失败',{exact:true}).waitFor();
 taskReadFailure=false;await drawer.getByRole('button',{name:'重试加载'}).click();await drawer.getByText('任务详情暂时失败',{exact:true}).waitFor({state:'hidden'});
 if(archivePosts!==1||revisionPosts!==2)throw new Error('读取重试重复写入');
 await drawer.getByRole('button',{name:'关闭此对话框',exact:true}).click();await drawer.waitFor({state:'hidden'});
 await page.getByRole('button',{name:'删除',exact:true}).click();let confirm=page.getByRole('dialog',{name:'删除任务',exact:true});await confirm.getByRole('button',{name:'确认删除'}).click();
 await page.getByText('任务删除失败',{exact:true}).waitFor();
 await page.getByRole('button',{name:'删除',exact:true}).click();await confirm.getByRole('button',{name:'确认删除'}).click();await page.getByText('暂无匹配任务',{exact:true}).waitFor();
 await page.getByRole('menuitem',{name:'成品库',exact:true}).click();const before=listReads,oldDetail=detailReads;
 await page.waitForTimeout(4300);if(listReads!==before||detailReads!==oldDetail)throw new Error('离页仍在轮询');
 await page.getByRole('heading',{name:'API成品 00',exact:true}).waitFor();
 archiveListFailure=true;await page.getByRole('textbox',{name:'搜索成品名称'}).fill('API成品');
 await page.getByText('成品列表暂时失败',{exact:true}).waitFor();if(await page.locator('.hx-library-card').count()!==12)throw new Error('读取失败清空旧列表');
 archiveListFailure=false;await page.getByRole('button',{name:'重试加载',exact:true}).click();
 await page.getByRole('button',{name:'下一页',exact:true}).click();await page.getByRole('heading',{name:'API成品 12',exact:true}).waitFor();
 await page.getByRole('textbox',{name:'搜索成品名称'}).fill('API成品 0');await page.getByRole('heading',{name:'API成品 00',exact:true}).waitFor();
 await page.getByRole('button',{name:'查看成品'}).first().click();let preview=page.getByRole('dialog',{name:'成品详情',exact:true});await preview.getByRole('button',{name:'关闭此对话框'}).click();
 await page.getByRole('button',{name:'查看成品'}).nth(1).click();await page.getByRole('dialog',{name:'API成品 01',exact:true}).waitFor();await page.waitForTimeout(600);
 preview=page.getByRole('dialog',{name:'API成品 01',exact:true});if(!await preview.isVisible())throw new Error('关闭后迟到详情覆盖新详情');await preview.getByRole('button',{name:'关闭此对话框'}).click();
 await page.getByRole('button',{name:'删除成品'}).first().click();confirm=page.getByRole('dialog',{name:'删除成品',exact:true});await confirm.getByRole('button',{name:'确认删除'}).click();await page.getByText('成品删除失败',{exact:true}).waitFor();
 await page.getByRole('heading',{name:'API成品 00',exact:true}).waitFor();await page.getByRole('button',{name:'删除成品'}).first().click();await confirm.getByRole('button',{name:'确认删除'}).click();await page.getByRole('heading',{name:'API成品 00',exact:true}).waitFor({state:'hidden'});
 if(errors.length)throw new Error(errors.join(';'));
 await page.unroute('**/api/v1/**');
 return 'PASS 任务/成品12+1分页、列表响应竞态、null进度、详情失败重试、返工意见保留、双击只1次重试写、写后读失败不重复、删除失败重试、离页停止轮询、成品读失败保留列表、关闭后迟到详情不覆盖，pageerror=0';
}
